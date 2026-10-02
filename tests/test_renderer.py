"""Тесты рендера: критерии приёмки A1 и A2.

A1 — отсчёт 10 с плюс hold 5 с на чёрном фоне даёт ролик 15 секунд, на 9-й
секунде `00:01`, с 10-й по 15-ю красный `00:00`, после текста нет.
A2 — секундомер на 8 секундах показывает на 5-й секунде `00:05`.

Проверка идёт по кадрам: тест достаёт кадр нужной секунды и сравнивает его
с эталоном либо с распознанным текстом. Покадровая обработка в самом
движке запрещена (NFR-02) — в тестовой части это допустимо.

Тесты с настоящим ffmpeg помечены `integration`: без ffmpeg или системного
шрифта они пропускаются, а не падают (FR-55).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from video_timer import osutil
from video_timer.config import TimerConfig, VideoTimerError
from video_timer.renderer import (
    LOG_TAIL_LINES,
    FFmpegRenderer,
    RenderCancelled,
    _new_log_tail,
    _progress_seconds,
    render,
)

from conftest import (
    drawtext_reference,
    ffmpeg_or_skip,
    frames_match,
    read_frame_gray,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def h264(monkeypatch: pytest.MonkeyPatch) -> str:
    """Дать имя кодировщика H.264, который собран в этой версии ffmpeg.

    Спека: FR-20, FR-22. Версия: v0.1.

    `TimerConfig.resolved_encoder()` в v0.1 возвращает константу `libx264`
    (FR-20), а проверка доступности кодека приходит в v0.2 (FR-22). Если в
    системе libx264 не собран, критерии A1 и A2 всё равно должны проверяться:
    корректность таймера от кодека не зависит. Поэтому в этом тесте
    `resolved_encoder()` подменяется на найденный кодировщик — правка
    интерфейса не проверяется, проверяется результат рендера.

    Args:
        monkeypatch: фикстура pytest для временной подмены метода.

    Returns:
        Имя кодировщика, которым будет записан тестовый ролик.

    Raises:
        pytest.skip.Exception: если ffmpeg или шрифт не найдены либо в сборке
            нет ни одного кодировщика H.264.
    """
    ffmpeg_or_skip()
    name = osutil.available_h264_encoder()
    if name is None:
        pytest.skip("в сборке ffmpeg нет кодировщика H.264")
    if name != "libx264":
        monkeypatch.setattr(TimerConfig, "resolved_encoder", lambda self: name)
    return name


@pytest.fixture
def countdown_cfg(tmp_path: Path) -> TimerConfig:
    """Конфигурация критерия A1: отсчёт 10 с, hold 5 с, чёрный фон.

    Спека: критерии A1, FR-02, FR-03. Версия: v0.1.

    Разрешение и размер шрифта уменьшены, чтобы кадр можно было сравнивать с
    эталоном из `conftest.drawtext_reference()`; на сам таймер это не влияет.

    Args:
        tmp_path: временная папка, которую создаёт pytest.

    Returns:
        `TimerConfig` для критерия A1, проходящая `validate()`.

    Raises:
        Не бросает исключений.
    """
    return TimerConfig(
        output=tmp_path / "a1.mp4",
        mode="countdown",
        countdown_seconds=10.0,
        hold_seconds=5.0,
        resolution="320x240",
        font_size=48,
    )


def probe_duration(path: Path) -> float | None:
    """Узнать длительность готового файла через ffprobe.

    Спека: критерии A1, A2, FR-11. Версия: v0.1.

    Args:
        path: путь к готовому ролику.

    Returns:
        Длительность в секундах или ``None``, если ffprobe недоступен.

    Raises:
        Не бросает исключений.
    """
    probe = osutil.find_ffprobe()
    if probe is None:
        return None
    finished = subprocess.run(
        [
            str(probe),
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(finished.stdout.strip())
    except ValueError:
        return None


def test_a1_countdown_10s_hold_5s(countdown_cfg: TimerConfig, h264: str) -> None:
    """A1: отсчёт 10 с и hold 5 с дают ролик длиной 15 с на чёрном фоне."""
    result = render(countdown_cfg)
    assert result.output == countdown_cfg.output
    assert result.output.exists()

    length = probe_duration(result.output)
    if length is None:
        pytest.skip("ffprobe не найден")
    assert length == pytest.approx(15.0, abs=0.2)


def test_a1_shows_00_01_at_ninth_second(
    countdown_cfg: TimerConfig, h264: str, tmp_path: Path
) -> None:
    """A1: на 9-й секунде на кадре видно `00:01`."""
    ffmpeg, font = ffmpeg_or_skip()
    render(countdown_cfg)

    reference = drawtext_reference(ffmpeg, font, "00:01", tmp_path / "ref.png")
    actual = read_frame_gray(ffmpeg, ["-ss", "9", "-i", str(countdown_cfg.output)])

    assert frames_match(actual, reference)


def test_a1_shows_red_00_00_from_tenth_to_fifteenth(
    countdown_cfg: TimerConfig, h264: str, tmp_path: Path
) -> None:
    """A1: с 10-й по 15-ю секунду горит красный `00:00`."""
    ffmpeg, font = ffmpeg_or_skip()
    render(countdown_cfg)

    reference = drawtext_reference(
        ffmpeg,
        font,
        "00:00",
        tmp_path / "hold.png",
        color=countdown_cfg.hold_color,
    )
    for second in ("10.5", "12", "14.5"):
        actual = read_frame_gray(
            ffmpeg, ["-ss", second, "-i", str(countdown_cfg.output)]
        )
        assert frames_match(actual, reference), f"кадр на {second} с не тот"


def test_a1_no_text_after_hold(tmp_path: Path, h264: str) -> None:
    """A1: после 15-й секунды таймера на кадре нет.

    Проверяется на видео-фоне длиннее окна hold. Сплошной цвет длиной ровно
    `N + hold` проверить нечем: за 15-й секундой в ролике нет ни одного кадра,
    и сравнивать не с чем. Поэтому источник здесь 20-секундный: в момент 12 с
    красный `00:00` ещё горит, а в момент 17 с на кадре остаётся только фон —
    ни основного текста, ни hold (FR-03).
    """
    ffmpeg, _font = ffmpeg_or_skip()
    source = tmp_path / "long.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:r=30:d=20",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        capture_output=True,
        check=True,
    )
    cfg = TimerConfig(
        output=tmp_path / "a1_long.mp4",
        background=source,
        duration=20.0,
        mode="countdown",
        countdown_seconds=10.0,
        hold_seconds=5.0,
        resolution="320x240",
        font_size=48,
    )
    render(cfg)

    inside_hold = read_frame_gray(ffmpeg, ["-ss", "12", "-i", str(cfg.output)])
    after_hold = read_frame_gray(ffmpeg, ["-ss", "17", "-i", str(cfg.output)])
    assert inside_hold is not None and after_hold is not None
    assert max(inside_hold) > 60, "в окне hold текст должен быть"
    assert max(after_hold) < 60, "после hold на кадре остался текст таймера"


def test_a2_stopwatch_8s_duration(
    tmp_output: Path, h264: str
) -> None:
    """A2: секундомер с `duration 8` даёт ролик длиной 8 с."""
    cfg = TimerConfig(
        output=tmp_output, duration=8.0, resolution="320x240", font_size=48
    )
    result = render(cfg)
    assert result.output.exists()

    length = probe_duration(result.output)
    if length is None:
        pytest.skip("ffprobe не найден")
    assert length == pytest.approx(8.0, abs=0.2)


def test_a2_shows_00_05_at_fifth_second(
    tmp_output: Path, h264: str, tmp_path: Path
) -> None:
    """A2: на 5-й секунде на кадре видно `00:05`."""
    ffmpeg, font = ffmpeg_or_skip()
    cfg = TimerConfig(
        output=tmp_output, duration=8.0, resolution="320x240", font_size=48
    )
    render(cfg)

    reference = drawtext_reference(ffmpeg, font, "00:05", tmp_path / "ref.png")
    actual = read_frame_gray(ffmpeg, ["-ss", "5", "-i", str(tmp_output)])

    assert frames_match(actual, reference)


def test_command_is_list_of_arguments(base_cfg: TimerConfig) -> None:
    """Команда ffmpeg собирается списком, `shell=True` не используется."""
    ffmpeg_or_skip()
    command = FFmpegRenderer(base_cfg).build_command()

    assert isinstance(command, list)
    assert all(isinstance(item, str) for item in command)


def test_command_contains_output_path(base_cfg: TimerConfig) -> None:
    """Последним аргументом идёт путь выходного файла (FR-20)."""
    ffmpeg_or_skip()
    command = FFmpegRenderer(base_cfg).build_command()

    assert command[-1] == str(base_cfg.output)
    assert "-y" in command


def test_command_uses_libx264_and_crf(base_cfg: TimerConfig) -> None:
    """Для libx264 в команде есть CRF и preset (FR-23)."""
    ffmpeg_or_skip()
    # resolved_encoder() в v0.1 возвращает libx264 постоянно (FR-20).
    command = FFmpegRenderer(base_cfg).build_command()

    assert "-c:v" in command
    assert command[command.index("-c:v") + 1] == "libx264"
    assert str(base_cfg.crf) in command
    assert base_cfg.preset in command
    assert "-r" in command


def test_command_omits_crf_for_other_encoder(
    base_cfg: TimerConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Кодек, кроме libx264, не получает CRF и preset: у него таких опций нет.

    В v0.1 `resolved_encoder()` возвращает константу (FR-20), поэтому
    не-libx264 кодек подставляется вручную: это проверка самого правила
    сборки команды, которое пригодится в v0.2 с `encoders.OUTPUT_CODECS`.
    """
    ffmpeg_or_skip()
    monkeypatch.setattr(TimerConfig, "resolved_encoder", lambda self: "mpeg4")

    command = FFmpegRenderer(base_cfg).build_command()

    assert command[command.index("-c:v") + 1] == "mpeg4"
    assert "-crf" not in command
    assert "-preset" not in command


def test_render_validates_before_running(base_cfg: TimerConfig, h264: str) -> None:
    """`render()` проверяет конфигурацию до запуска ffmpeg (FR-40)."""
    base_cfg.font_size = 0
    with pytest.raises(VideoTimerError) as caught:
        render(base_cfg)

    assert str(caught.value).startswith("font-size:")


def test_a7_ffmpeg_not_started_on_invalid_config(
    base_cfg: TimerConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A7: при `font-size 0` процесс ffmpeg не запускается вовсе."""
    base_cfg.font_size = 0
    started: list[list[str]] = []
    real_popen = subprocess.Popen

    def watching_popen(*args: object, **kwargs: object) -> subprocess.Popen:
        started.append([str(item) for item in args[0]])  # type: ignore[index]
        return real_popen(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(subprocess, "Popen", watching_popen)
    with pytest.raises(VideoTimerError):
        render(base_cfg)

    assert started == []


def test_output_parent_dir_created(tmp_path: Path, h264: str) -> None:
    """FR-41: `render()` создаёт отсутствующую папку результата.

    Спека: FR-41. Версия: v0.1.

    Пользователь вводит путь, куда хочет получить ролик, и получает файл
    именно там. Без этого ffmpeg падает с `No such file or directory`, а
    сообщение об ошибке ссылается на ffmpeg вместо проблемного поля.

    Args:
        tmp_path: временная папка, которую создаёт pytest.
        h264: имя доступного кодировщика H.264, см. фикстуру `h264`.
    """
    cfg = TimerConfig(
        output=tmp_path / "глубоко" / "вложенная" / "папка" / "out.mp4",
        duration=1.0,
    )
    assert not cfg.output.parent.exists()

    result = render(cfg)

    assert cfg.output.parent.is_dir()
    assert result.output.is_file()
    assert result.output == cfg.output


def test_render_twice_to_existing_dir(tmp_path: Path, h264: str) -> None:
    """FR-41: повторный рендер в ту же папку не падает.

    Спека: FR-41. Версия: v0.1.

    GUI даёт один и тот же каталог для всех роликов, поэтому папка вывода
    существует почти всегда. Создание папки должно быть идемпотентным, иначе
    второй рендер в тот же путь падал бы с понятной, но лишней ошибкой.

    Args:
        tmp_path: временная папка, которую создаёт pytest.
        h264: имя доступного кодировщика H.264, см. фикстуру `h264`.
    """
    cfg = TimerConfig(output=tmp_path / "первый.mp4", duration=1.0)
    render(cfg)
    assert cfg.output.parent.is_dir()

    second = TimerConfig(output=tmp_path / "второй.mp4", duration=1.0)
    result = render(second)

    assert result.output.is_file()


def test_output_dir_taken_by_file_gives_readable_error(tmp_path: Path) -> None:
    """FR-41: если на месте папки лежит файл, пользователь получает понятное
    сообщение со своим полем, а не текст ffmpeg.

    Спека: FR-41, FR-42. Версия: v0.1.

    Args:
        tmp_path: временная папка, которую создаёт pytest.
    """
    blocker = tmp_path / "занято"
    blocker.write_text("я файл, а не папка", encoding="utf-8")
    cfg = TimerConfig(output=blocker / "out.mp4", duration=1.0)

    with pytest.raises(VideoTimerError) as caught:
        render(cfg)

    message = str(caught.value)
    assert message.startswith("output: "), message
    assert str(blocker) in message, message
    assert "Traceback" not in message


def test_error_message_contains_field_prefix(tmp_path: Path) -> None:
    """Пользователю возвращается «поле: что не так», а не лог ffmpeg (FR-42).

    Подставляется файл с расширением `.mp4`, внутри которого не видео: он
    проходит `validate()` (FR-10 проверяет существование), но ffmpeg падает.
    Так проверяется именно сообщение о сбое рендера, а не отказ конфигурации.
    """
    ffmpeg_or_skip()
    broken = tmp_path / "битый.mp4"
    broken.write_text("это не видео" * 64, encoding="utf-8")
    cfg = TimerConfig(output=tmp_path / "out.mp4", background=broken, duration=1.0)

    with pytest.raises(VideoTimerError) as caught:
        render(cfg)

    message = str(caught.value)
    assert message.startswith("render:"), message
    assert "Traceback" not in message


def test_error_message_explains_cause_without_banner(tmp_path: Path) -> None:
    """Сообщение короткое и содержит причину, а не баннер сборки (FR-42).

    Проверяется, что в сообщение попадают последние строки лога: ffmpeg
    печатает причину ошибки последней, а до неё — перечень кодеков на
    несколько тысяч символов, который пользователю ничего не объясняет.
    """
    ffmpeg_or_skip()
    cfg = TimerConfig(output=tmp_path / "нет-такой-папки" / "out.mp4", duration=1.0)

    with pytest.raises(VideoTimerError) as caught:
        render(cfg)

    message = str(caught.value)
    assert len(message) < 1000, "в сообщение попал весь лог ffmpeg"
    assert "pcm_s16le" not in message, "в сообщение попал баннер сборки"
    assert "No such file or directory" in message or "Error" in message


def test_progress_line_parsed_as_microseconds() -> None:
    """`out_time_us` и `out_time_ms` ffmpeg читаются как микросекунды (FR-51).

    Поле `out_time_ms` названо в миллисекундах, но ffmpeg пишет в нём
    микросекунды. Если поверить названию, прогрессбар будет в 1000 раз
    быстрее реальности и сразу покажет 100 %.
    """
    assert _progress_seconds("out_time_us=15000000") == pytest.approx(15.0)
    assert _progress_seconds("out_time_ms=15000000") == pytest.approx(15.0)
    assert _progress_seconds("out_time=00:00:15.000000") is None
    assert _progress_seconds("progress=continue") is None
    assert _progress_seconds("бинарный мусор") is None


def test_log_tail_keeps_fifty_lines() -> None:
    """В памяти остаётся не более 50 последних строк лога (NFR-04)."""
    assert LOG_TAIL_LINES == 50
    tail = _new_log_tail()
    for number in range(200):
        tail.append(f"строка {number}")

    assert len(tail) == 50
    assert tail[-1] == "строка 199"


def test_progress_callback_reports_fraction(
    countdown_cfg: TimerConfig, h264: str
) -> None:
    """Колбэк прогресса получает долю от 0 до 1 (FR-51)."""
    fractions: list[float] = []
    render(countdown_cfg, lambda done, _total: fractions.append(done))

    assert fractions, "колбэк прогресса не вызывался"
    assert all(0.0 <= value <= 1.0 for value in fractions)
    assert fractions[-1] == pytest.approx(1.0, abs=0.05)
    assert fractions == sorted(fractions)


def test_progress_callback_reports_total_seconds(
    countdown_cfg: TimerConfig, h264: str
) -> None:
    """Колбэк прогресса получает общую длительность, когда она известна."""
    totals: list[float | None] = []
    render(countdown_cfg, lambda _done, total: totals.append(total))

    assert totals
    assert all(total == pytest.approx(15.0) for total in totals)


def test_progress_total_is_none_for_unknown_length(
    tmp_path: Path, h264: str
) -> None:
    """Для видео-фона без известной длительности второй аргумент равен ``None``."""
    ffmpeg, _font = ffmpeg_or_skip()
    source = tmp_path / "clip.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=320x240:r=30:d=2",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        capture_output=True,
        check=True,
    )
    cfg = TimerConfig(
        output=tmp_path / "out.mp4",
        background=source,
        resolution="320x240",
        font_size=48,
    )

    totals: list[float | None] = []
    render(cfg, lambda _done, total: totals.append(total))

    assert totals
    assert all(total is None for total in totals)


def test_render_result_carries_output(
    base_cfg: TimerConfig, h264: str
) -> None:
    """`RenderResult.output` указывает на записанный файл."""
    result = render(base_cfg)

    assert result.output == base_cfg.output
    assert result.output.exists()
    assert result.duration_seconds is None or result.duration_seconds > 0
    assert isinstance(result.tail_log, str)


def test_missing_ffmpeg_raises_readable_error(
    base_cfg: TimerConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Без ffmpeg — понятное сообщение с инструкцией, а не `FileNotFoundError`."""
    monkeypatch.setattr(osutil, "find_ffmpeg", lambda: None)

    with pytest.raises(VideoTimerError) as caught:
        FFmpegRenderer(base_cfg)

    message = str(caught.value)
    assert message.startswith("ffmpeg:")
    assert "установ" in message.lower()


def test_cancel_stops_running_ffmpeg(base_cfg: TimerConfig) -> None:
    """Отмена останавливает процесс ffmpeg (v0.2, критерий A9)."""
    pytest.fail("не реализовано: A9 — cancel() останавливает ffmpeg")


def test_cancel_before_start_is_safe(base_cfg: TimerConfig) -> None:
    """Отмена до старта рендера не бросает исключений (v0.2)."""
    pytest.fail("не реализовано: FR-51 — cancel() без запуска безопасен")


def test_cancelled_render_raises_render_cancelled(base_cfg: TimerConfig) -> None:
    """Остановленный рендер поднимает `RenderCancelled`, не `VideoTimerError`."""
    pytest.fail("не реализовано: FR-51 — отмена отличается от ошибки")


def test_render_cancelled_is_video_timer_error() -> None:
    """`RenderCancelled` наследуется от `VideoTimerError` (SPEC 7.6)."""
    assert issubclass(RenderCancelled, VideoTimerError)


def test_renderer_callable_without_ffmpeg(base_cfg: TimerConfig) -> None:
    """Конструктор `FFmpegRenderer` доступен и без запуска ffmpeg."""
    ffmpeg_or_skip()
    renderer = FFmpegRenderer(base_cfg)

    assert isinstance(renderer, FFmpegRenderer)
    assert renderer.build_command()


def test_render_is_callable_helper(base_cfg: TimerConfig) -> None:
    """Модуль-функция `render()` — единая точка входа для CLI и GUI (FR-50)."""
    ffmpeg_or_skip()
    assert callable(render)
    assert render.__doc__
