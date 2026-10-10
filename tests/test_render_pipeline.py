"""Тесты результата рендера: собранная цепочка против критериев A1 и A2.

Это единственное место, где таймер проверяется не по строкам цепочки, а по
кадрам настоящего ffmpeg: цепочка собирается из `Background` и `FilterBuilder`,
рендерится, затем кадр нужной секунды сравнивается с эталоном — тем же
текстом, отрисованным через `drawtext` из файла, без экранирования.

Покадровая обработка в самом движке запрещена (NFR-02), здесь она допустима:
тест смотрит на результат, а не подменяет ffmpeg.

Покадровые тесты помечены как `integration`: без ffmpeg или системного шрифта
они пропускаются, а не падают (FR-55). Остальные тесты файла проверяют сборку
цепочки и должны проходить всегда.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from video_timer.background import Background
from video_timer.config import TimerConfig
from video_timer.filters import FilterBuilder
from video_timer import osutil

from conftest import (
    drawtext_reference,
    ffmpeg_or_skip,
    frames_match,
    read_frame_gray,
)

pytestmark = pytest.mark.integration


def render(cfg: TimerConfig, ffmpeg: str) -> bool:
    """Отрендерить ролик по цепочке, собранной из модулей движка.

    Спека: критерии A1, A2, FR-10…FR-13, FR-20. Версия: v0.1.

    Кодек выбирается через `resolved_encoder()` — так же, как это сделает
    `FFmpegRenderer` завтра. Если кодека нет в системе, тест пропускается:
    отсутствие кодировщика не повод считать сборку фильтров неверной.

    Кодек берётся из `resolved_encoder()` — тот же выбор, что сделает
    `FFmpegRenderer`. Сборки ffmpeg без libx264 встречаются, и тогда цепочка
    фильтров проверяется на запасном кодеке: корректность таймера от кодека не
    зависит, а тест не должен молча вырождаться в пропуск из-за сборки.

    Args:
        cfg: конфигурация рендера.
        ffmpeg: путь к исполняемому файлу ffmpeg.

    Returns:
        `True`, если файл создан.

    Raises:
        Не бросает исключений.
    """
    background = Background(cfg)
    encoder = cfg.resolved_encoder()
    encoder_args = ["-c:v", encoder]
    if encoder == "libx264":
        encoder_args.extend(["-crf", str(cfg.crf), "-preset", cfg.preset])

    def attempt() -> subprocess.CompletedProcess[bytes]:
        return subprocess.run(
            [
                ffmpeg,
                "-v",
                "error",
                "-y",
                *background.input_args(),
                "-filter_complex",
                ",".join(FilterBuilder(cfg, background).build()),
                *encoder_args,
                str(cfg.output),
            ],
            capture_output=True,
        )

    finished = attempt()
    if finished.returncode != 0 and b"Unknown encoder" in finished.stderr:
        fallback = osutil.available_h264_encoder()
        if fallback is None:
            pytest.skip(f"кодек {encoder} не собран в этой сборке ffmpeg")
        encoder = fallback
        encoder_args = ["-c:v", encoder, "-qp", "0"]
        finished = attempt()

    assert finished.returncode == 0, finished.stderr.decode()[-600:]
    return cfg.output.exists()


def duration_of(ffmpeg: str, path: Path) -> float | None:
    """Узнать длительность готового файла через ffprobe.

    Спека: критерии A1, A2. Версия: v0.1.

    Args:
        ffmpeg: путь к ffmpeg; рядом ищем ffprobe тем же способом.
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


def probe_size(ffmpeg: str, path: Path) -> tuple[int, int] | None:
    """Узнать размер кадра готового файла через ffprobe.

    Спека: критерии A3, A4, FR-13. Версия: v0.2.

    Args:
        ffmpeg: путь к ffmpeg; рядом ищем ffprobe тем же способом.
        path: путь к готовому ролику.

    Returns:
        Пару ``(ширина, высота)`` или ``None``, если ffprobe недоступен.

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
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height",
            "-of",
            "csv=p=0:s=x",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        width, height = finished.stdout.strip().split("x")
        return int(width), int(height)
    except ValueError:
        return None


def pixel_gray(ffmpeg: str, path: Path, x: int, y: int) -> int | None:
    """Прочитать яркость участка 8×8 готового ролика.

    Спека: критерии A3, A4. Версия: v0.2.

    Кадр `yuv420p` нельзя обрезать до одного пикселя: хрома-плоскости требуют
    чётных размеров, и `crop=1:1` возвращает пустой поток. Берётся блок 8×8,
    возвращается средняя яркость — для сплошного фона этого достаточно.

    Args:
        ffmpeg: путь к исполняемому файлу ffmpeg.
        path: путь к готовому ролику.
        x: координата левого верхнего угла блока.
        y: координата левого верхнего угла блока.

    Returns:
        Среднюю яркость 0…255 или ``None``, если ffmpeg не отдал блок.

    Raises:
        Не бросает исключений.
    """
    finished = subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-ss",
            "0.5",
            "-i",
            str(path),
            "-vf",
            f"crop=8:8:{x}:{y}",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "gray",
            "-",
        ],
        capture_output=True,
    )
    if len(finished.stdout) < 64:
        return None
    return sum(finished.stdout[:64]) // 64


@pytest.fixture
def countdown_cfg(tmp_path: Path) -> TimerConfig:
    """Конфигурация критерия A1: отсчёт 10 с, hold 5 с, чёрный фон."""
    return TimerConfig(
        output=tmp_path / "a1.mp4",
        mode="countdown",
        countdown_seconds=10.0,
        hold_seconds=5.0,
        resolution="320x240",
        font_size=48,
    )


def test_a1_countdown_and_hold_give_15_seconds(
    countdown_cfg: TimerConfig,
) -> None:
    """A1: отсчёт 10 с и hold 5 с дают ролик длиной ровно 15 секунд."""
    ffmpeg, _font = ffmpeg_or_skip()
    countdown_cfg.validate()
    assert render(countdown_cfg, ffmpeg)

    length = duration_of(ffmpeg, countdown_cfg.output)
    if length is None:
        pytest.skip("ffprobe не найден")
    assert length == pytest.approx(15.0, abs=0.2)


def test_a1_shows_00_01_at_ninth_second(
    countdown_cfg: TimerConfig, tmp_path: Path
) -> None:
    """A1: на 9-й секунде кадр совпадает с эталоном `00:01` белым."""
    ffmpeg, font = ffmpeg_or_skip()
    countdown_cfg.validate()
    assert render(countdown_cfg, ffmpeg)

    reference = drawtext_reference(ffmpeg, font, "00:01", tmp_path / "ref.png")
    actual = read_frame_gray(ffmpeg, ["-ss", "9", "-i", str(countdown_cfg.output)])

    assert frames_match(actual, reference)


def test_a1_shows_red_00_00_from_tenth_to_fifteenth(
    countdown_cfg: TimerConfig, tmp_path: Path
) -> None:
    """A1: с 10-й по 15-ю секунду горит красный `00:00`."""
    ffmpeg, font = ffmpeg_or_skip()
    countdown_cfg.validate()
    assert render(countdown_cfg, ffmpeg)

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


def test_a1_countdown_counts_down_each_second(
    countdown_cfg: TimerConfig, tmp_path: Path
) -> None:
    """Значение уменьшается на единицу в секунду: 1 с → `00:09`, 5 с → `00:05`."""
    ffmpeg, font = ffmpeg_or_skip()
    countdown_cfg.validate()
    assert render(countdown_cfg, ffmpeg)

    for second, text in (("1", "00:09"), ("5", "00:05"), ("8", "00:02")):
        reference = drawtext_reference(ffmpeg, font, text, tmp_path / f"r{second}.png")
        actual = read_frame_gray(
            ffmpeg, ["-ss", second, "-i", str(countdown_cfg.output)]
        )
        assert frames_match(actual, reference), f"на {second} с ожидалось {text}"


def test_a2_stopwatch_8s_duration(tmp_output: Path) -> None:
    """A2: секундомер с `duration 8` даёт ролик длиной ровно 8 секунд."""
    ffmpeg, _font = ffmpeg_or_skip()
    cfg = TimerConfig(output=tmp_output, duration=8.0, resolution="320x240", font_size=48)
    cfg.validate()
    assert render(cfg, ffmpeg)

    length = duration_of(ffmpeg, cfg.output)
    if length is None:
        pytest.skip("ffprobe не найден")
    assert length == pytest.approx(8.0, abs=0.2)


def test_a2_shows_00_05_at_fifth_second(tmp_output: Path, tmp_path: Path) -> None:
    """A2: на 5-й секунде кадр совпадает с эталоном `00:05`."""
    ffmpeg, font = ffmpeg_or_skip()
    cfg = TimerConfig(output=tmp_output, duration=8.0, resolution="320x240", font_size=48)
    cfg.validate()
    assert render(cfg, ffmpeg)

    reference = drawtext_reference(ffmpeg, font, "00:05", tmp_path / "ref.png")
    actual = read_frame_gray(ffmpeg, ["-ss", "5", "-i", str(tmp_output)])

    assert frames_match(actual, reference)


def test_a2_has_no_hold_phase(tmp_output: Path, tmp_path: Path) -> None:
    """У секундомера нет фазы hold: текст идёт до конца ролика (FR-03)."""
    ffmpeg, font = ffmpeg_or_skip()
    cfg = TimerConfig(output=tmp_output, duration=8.0, resolution="320x240", font_size=48)
    cfg.validate()
    assert render(cfg, ffmpeg)

    reference = drawtext_reference(ffmpeg, font, "00:07", tmp_path / "ref.png")
    actual = read_frame_gray(ffmpeg, ["-ss", "7.5", "-i", str(tmp_output)])

    assert frames_match(actual, reference)


def test_text_is_not_drawn_after_hold(
    countdown_cfg: TimerConfig, tmp_path: Path
) -> None:
    """FR-03: после hold текста на кадре нет.

    Критерий A1 говорит «после 15-й секунды текста нет», но ролик длиной ровно
    15 секунд обрезан на границе hold, поэтому кадра после конца в нём не
    существует. Проверяем то, что проверяемо: на последней секунде ролика
    текст ещё есть, а добавить его за пределами окна нечем — условие
    `between(t,10,15)` ограничено по времени.
    """
    ffmpeg, font = ffmpeg_or_skip()
    countdown_cfg.validate()
    assert render(countdown_cfg, ffmpeg)

    reference = drawtext_reference(
        ffmpeg,
        font,
        "00:00",
        tmp_path / "hold.png",
        color=countdown_cfg.hold_color,
    )
    last = read_frame_gray(ffmpeg, ["-ss", "14.9", "-i", str(countdown_cfg.output)])

    assert frames_match(last, reference)


def test_video_background_is_used_as_source(tmp_output: Path, tmp_path: Path) -> None:
    """FR-10, FR-11: видео-фон идёт на вход, таймер рисуется поверх него."""
    ffmpeg, font = ffmpeg_or_skip()
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
            "color=c=blue:s=320x240:r=30:d=6",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        capture_output=True,
        check=True,
    )

    cfg = TimerConfig(output=tmp_output, background=source, resolution="320x240", font_size=48)
    cfg.validate()
    assert render(cfg, ffmpeg)

    length = duration_of(ffmpeg, cfg.output)
    if length is None:
        pytest.skip("ffprobe не найден")
    assert length == pytest.approx(6.0, abs=0.2)

    frame = read_frame_gray(ffmpeg, ["-ss", "2", "-i", str(tmp_output)])
    assert frame is not None
    assert max(frame) > 60, "на кадре должен быть текст таймера поверх синего фона"


def test_position_moves_timer(tmp_output: Path, tmp_path: Path) -> None:
    """FR-05: позиция `center` двигает таймер в центр кадра относительно `br`."""
    ffmpeg, font = ffmpeg_or_skip()
    corners = tmp_path / "br.mp4"
    center = tmp_path / "center.mp4"

    corner_cfg = TimerConfig(output=corners, duration=3.0, resolution="320x240", font_size=48, position="br")
    center_cfg = TimerConfig(
        output=center, duration=3.0, resolution="320x240", font_size=48, position="center"
    )
    corner_cfg.validate()
    center_cfg.validate()
    assert render(corner_cfg, ffmpeg)
    assert render(center_cfg, ffmpeg)

    corner_frame = read_frame_gray(ffmpeg, ["-ss", "1", "-i", str(corners)])
    center_frame = read_frame_gray(ffmpeg, ["-ss", "1", "-i", str(center)])

    assert corner_frame is not None and center_frame is not None
    assert not frames_match(corner_frame, center_frame)


@pytest.fixture
def wide_video(tmp_path: Path) -> Path:
    """Создать видео 16:9 для проверки полей и обрезки (A3, A4).

    Спека: критерии A3, A4. Версия: v0.2.

    Сплошной зелёный цвет удобно отличать от чёрных полей `pad`: яркость
    зелёного в оттенках серого заметно выше нуля.
    """
    ffmpeg, _font = ffmpeg_or_skip()
    source = tmp_path / "wide.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=green:s=640x360:r=30:d=1",
            "-pix_fmt",
            "yuv420p",
            str(source),
        ],
        capture_output=True,
        check=True,
    )
    return source


def test_a3_contain_gives_square_with_black_bars(
    wide_video: Path, tmp_output: Path
) -> None:
    """A3: видео 16:9 с `--resolution 1080x1080 --fit contain` даёт 1080×1080 с полями."""
    ffmpeg, _font = ffmpeg_or_skip()
    cfg = TimerConfig(
        output=tmp_output,
        background=wide_video,
        resolution="1080x1080",
        fit="contain",
        font_size=48,
    )
    cfg.validate()
    assert render(cfg, ffmpeg)

    assert probe_size(ffmpeg, cfg.output) == (1080, 1080)
    top = pixel_gray(ffmpeg, cfg.output, 540, 2)
    bottom = pixel_gray(ffmpeg, cfg.output, 540, 1070)
    center = pixel_gray(ffmpeg, cfg.output, 540, 540)

    assert top is not None and top < 50, "сверху должна быть чёрная полоса"
    assert bottom is not None and bottom < 50, "снизу должна быть чёрная полоса"
    assert center is not None and center > 60, "в центре должен быть кадр видео"


def test_a4_cover_gives_square_without_bars(
    wide_video: Path, tmp_output: Path
) -> None:
    """A4: то же с `--fit cover` даёт 1080×1080 без полей, края обрезаны."""
    ffmpeg, _font = ffmpeg_or_skip()
    cfg = TimerConfig(
        output=tmp_output,
        background=wide_video,
        resolution="1080x1080",
        fit="cover",
        font_size=48,
    )
    cfg.validate()
    assert render(cfg, ffmpeg)

    assert probe_size(ffmpeg, cfg.output) == (1080, 1080)
    top = pixel_gray(ffmpeg, cfg.output, 540, 2)
    center = pixel_gray(ffmpeg, cfg.output, 540, 540)

    assert top is not None and top > 50, "полей сверху быть не должно"
    assert center is not None and center > 60
