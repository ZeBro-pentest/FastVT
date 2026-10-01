"""Тесты фона: видеофайл и сплошной цвет.

Фон — то, что подаётся на вход ffmpeg. Сегодня закрываются FR-10 (тип
фона), FR-11 (длительность из ffprobe) и FR-12 (сплошной цвет даёт конечную
длительность без файла). Картинка остаётся на v0.2.
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