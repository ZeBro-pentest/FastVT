"""Тесты фона: видеофайл, картинка и сплошной цвет.

Фон — то, что подаётся на вход ffmpeg. Закрываются FR-10 (тип фона),
FR-11 (длительность видео из ffprobe), FR-12 (картинка и цвет дают конечную
длительность без файла) и FR-15 (звук видео-фона).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from video_timer import background as background_module
from video_timer.background import Background
from video_timer.config import TimerConfig, VideoTimerError


def make_video(path: Path, seconds: float = 5.0) -> Path:
    """Создать настоящий видеофайл через ffmpeg, чтобы ffprobe его прочитал."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=blue:s=320x240:r=10:d={seconds}",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


def make_video_with_audio(path: Path, seconds: float = 3.0) -> Path:
    """Создать видеофайл со звуковой дорожкой для FR-15."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"color=c=blue:s=320x240:r=10:d={seconds}",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={seconds}",
            "-shortest",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


def make_image(path: Path) -> Path:
    """Создать настоящую картинку `.png` через ffmpeg."""
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=320x240",
            "-frames:v",
            "1",
            str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


def test_color_kind_is_color(base_cfg: TimerConfig) -> None:
    """Без файла фон — сплошной цвет (FR-10)."""
    assert Background(base_cfg).kind == "color"


def test_video_kind_is_video(tmp_output: Path, tmp_path: Path) -> None:
    """Файл с видеорасширением даёт `kind == "video"` (FR-10)."""
    source = make_video(tmp_path / "clip.mp4")
    cfg = TimerConfig(output=tmp_output, background=source)

    assert Background(cfg).kind == "video"


def test_missing_file_rejected(tmp_output: Path) -> None:
    """Путь, которого нет на диске, даёт `background: файл не найден` (FR-10)."""
    cfg = TimerConfig(output=tmp_output, background=Path("/tmp/нет-такого.mp4"))

    with pytest.raises(VideoTimerError, match=r"^background: файл не найден"):
        Background(cfg)


def test_unsupported_extension_rejected(tmp_output: Path, tmp_path: Path) -> None:
    """Расширение не из списка даёт `background: тип файла не поддерживается` (FR-10)."""
    source = tmp_path / "notes.txt"
    source.write_text("не видео", encoding="utf-8")
    cfg = TimerConfig(output=tmp_output, background=source)

    with pytest.raises(
        VideoTimerError, match=r"^background: тип файла не поддерживается"
    ):
        Background(cfg)


def test_color_duration_from_config(base_cfg: TimerConfig) -> None:
    """Для цвета длительность берётся из `cfg.duration`, ffprobe не нужен (FR-11)."""
    assert Background(base_cfg).probe_duration() == pytest.approx(8.0)


def test_video_duration_probed_with_ffprobe(
    tmp_output: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Длительность видео-фона читается из ffprobe (FR-11)."""
    source = make_video(tmp_path / "clip.mp4", seconds=3.0)
    monkeypatch.setattr(background_module, "_run_ffprobe", lambda *a: 3.0)
    cfg = TimerConfig(output=tmp_output, background=source)

    assert Background(cfg).probe_duration() == pytest.approx(3.0)


def test_probe_duration_none_without_ffprobe(
    tmp_output: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Нет ffprobe — `None`, а не исключение: рендер продолжает работу (FR-11)."""
    source = make_video(tmp_path / "clip.mp4")
    monkeypatch.setattr(
        background_module.osutil,
        "find_ffprobe",
        lambda: None,
    )
    cfg = TimerConfig(output=tmp_output, background=source)

    assert Background(cfg).probe_duration() is None


def test_probe_duration_probed_only_once(
    tmp_output: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Результат ffprobe запоминается: файл не зондируется повторно (SPEC 7.5)."""
    calls: list[tuple[object, ...]] = []

    def fake(*args: object) -> float:
        calls.append(args)
        return 2.5

    source = make_video(tmp_path / "clip.mp4")
    monkeypatch.setattr(background_module, "_run_ffprobe", fake)
    bg = Background(TimerConfig(output=tmp_output, background=source))

    assert bg.probe_duration() == pytest.approx(2.5)
    assert bg.probe_duration() == pytest.approx(2.5)
    assert len(calls) == 1


def test_color_input_args_use_lavfi_color(base_cfg: TimerConfig) -> None:
    """Сплошной цвет даёт `-f lavfi -i color=c=…:d=…` (FR-12)."""
    args = Background(base_cfg).input_args()

    assert args[:2] == ["-f", "lavfi"]
    source = args[args.index("-i") + 1]
    assert source.startswith("color=c=black:")
    assert "d=8.0" in source or "d=8" in source


def test_color_input_args_have_resolution_and_rate(base_cfg: TimerConfig) -> None:
    """У цвета обязательно есть размер и частота кадров, иначе ffmpeg не примет."""
    source = Background(base_cfg).input_args()[-1]

    assert "s=" in source
    assert "r=" in source


def test_color_default_resolution_is_1920x1080(base_cfg: TimerConfig) -> None:
    """Цвет без `resolution` рендерится в 1920x1080 (v0.2, SPEC 4.1)."""
    source = Background(base_cfg).input_args()[-1]

    assert "s=1920x1080" in source


def test_resolution_overrides_color_default(base_cfg: TimerConfig) -> None:
    """Заданный `resolution` перебивает размер цвета по умолчанию (FR-13)."""
    base_cfg.resolution = "1080x1080"
    source = Background(base_cfg).input_args()[-1]

    assert "s=1080x1080" in source


def test_video_input_args_are_input_then_path(tmp_output: Path, tmp_path: Path) -> None:
    """Видео-фон даёт `-i <путь>`, путь идёт строкой (FR-10)."""
    source = make_video(tmp_path / "clip.mp4")
    args = Background(TimerConfig(output=tmp_output, background=source)).input_args()

    assert args == ["-i", str(source)]


def test_video_input_args_add_duration_limit(
    tmp_output: Path, tmp_path: Path
) -> None:
    """Заданный `cfg.duration` добавляет `-t`, чтобы обрезать источник (FR-11)."""
    source = make_video(tmp_path / "clip.mp4", seconds=5.0)
    cfg = TimerConfig(output=tmp_output, background=source, duration=2.0)
    args = Background(cfg).input_args()

    assert args[0] == "-i"
    assert "-t" in args
    assert args[args.index("-t") + 1] in {"2", "2.0"}


def test_input_args_without_duration_have_no_limit(
    tmp_output: Path, tmp_path: Path
) -> None:
    """Без `cfg.duration` флаг `-t` не добавляется: источник не режется (FR-11)."""
    source = make_video(tmp_path / "clip.mp4")
    cfg = TimerConfig(output=tmp_output, background=source)
    cfg.duration = None
    args = Background(cfg).input_args()

    assert "-t" not in args


def test_image_kind_is_image(tmp_output: Path, tmp_path: Path) -> None:
    """Файл с расширением картинки даёт `kind == "image"` (FR-10)."""
    source = make_image(tmp_path / "bg.png")
    cfg = TimerConfig(output=tmp_output, background=source, duration=4.0)

    assert Background(cfg).kind == "image"


def test_image_input_args_use_loop(tmp_output: Path, tmp_path: Path) -> None:
    """Картинка зацикливается флагом `-loop 1` и ограничивается `-t` (FR-10, FR-12)."""
    source = make_image(tmp_path / "bg.png")
    cfg = TimerConfig(output=tmp_output, background=source, duration=4.0)

    args = Background(cfg).input_args()

    assert args[:4] == ["-loop", "1", "-i", str(source)]
    assert args[args.index("-t") + 1] in {"4", "4.0"}


def test_image_duration_from_config(
    tmp_output: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Для картинки длительность берётся из `cfg.duration`, без ffprobe (FR-12)."""
    source = make_image(tmp_path / "bg.png")

    def forbidden(*_args: object) -> float:
        raise AssertionError("ffprobe не должен вызываться для картинки")

    monkeypatch.setattr(background_module, "_run_ffprobe", forbidden)
    cfg = TimerConfig(output=tmp_output, background=source, duration=6.5)

    assert Background(cfg).probe_duration() == pytest.approx(6.5)


def test_image_duration_is_countdown_plus_hold(
    tmp_output: Path, tmp_path: Path
) -> None:
    """Для отсчёта картинка живёт `countdown + hold`, `duration` не нужен (FR-12)."""
    source = make_image(tmp_path / "bg.png")
    cfg = TimerConfig(
        output=tmp_output,
        background=source,
        mode="countdown",
        countdown_seconds=10.0,
        hold_seconds=5.0,
    )

    assert Background(cfg).probe_duration() == pytest.approx(15.0)


def test_color_has_no_audio(base_cfg: TimerConfig) -> None:
    """Сплошной цвет беззвучный: дорожка не создаётся (FR-15)."""
    assert Background(base_cfg).has_audio() is False


def test_image_has_no_audio(tmp_output: Path, tmp_path: Path) -> None:
    """Картинка беззвучная: дорожка не создаётся (FR-15)."""
    source = make_image(tmp_path / "bg.png")
    cfg = TimerConfig(output=tmp_output, background=source, duration=4.0)

    assert Background(cfg).has_audio() is False


def test_video_with_audio_detected(tmp_output: Path, tmp_path: Path) -> None:
    """Видео-фон со звуком распознаётся через ffprobe (FR-15)."""
    source = make_video_with_audio(tmp_path / "av.mp4")
    cfg = TimerConfig(output=tmp_output, background=source)

    assert Background(cfg).has_audio() is True


def test_video_without_audio_detected(tmp_output: Path, tmp_path: Path) -> None:
    """Видео-фон без звука даёт `has_audio() is False` (FR-15)."""
    source = make_video(tmp_path / "clip.mp4")
    cfg = TimerConfig(output=tmp_output, background=source)

    assert Background(cfg).has_audio() is False


def test_video_audio_probed_only_once(
    tmp_output: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Результат проверки звука запоминается: файл не зондируется повторно (FR-15)."""
    calls: list[tuple[object, ...]] = []

    def fake(*args: object) -> bool:
        calls.append(args)
        return True

    source = make_video(tmp_path / "clip.mp4")
    monkeypatch.setattr(background_module, "_run_ffprobe_audio", fake)
    bg = Background(TimerConfig(output=tmp_output, background=source))

    assert bg.has_audio() is True
    assert bg.has_audio() is True
    assert len(calls) == 1