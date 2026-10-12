"""Тесты выбора кодека вывода: критерии A5 и A6.

A5 — вывод в `.webm` даёт играбельный файл с кодеком VP9.
A6 — `.webm` вместе с `--encoder libx264` отклоняется сообщением
`«encoder: …»`, и рендер ffmpeg не запускается.

Модульные тесты проверяют `encoders.pick_encoder()` и `available_encoders()`
без настоящего ffmpeg: поиск сборки и список кодеков подменяются. Рендер
целиком (A5) помечен `integration` и пропускается, если в сборке нет
`libvpx-vp9` или ffprobe.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from video_timer import encoders, osutil
from video_timer.config import TimerConfig, VideoTimerError
from video_timer.renderer import render

from conftest import ffmpeg_or_skip

INTEGRATION = pytest.mark.integration


def test_output_codecs_cover_all_formats() -> None:
    """Таблица кодирует все четыре контейнера и кодек VP9 для `.webm` (FR-20)."""
    assert set(encoders.OUTPUT_CODECS) == {".mp4", ".mov", ".mkv", ".webm"}
    assert encoders.OUTPUT_CODECS[".webm"] == {
        "video": "libvpx-vp9",
        "audio": "libopus",
    }
    assert encoders.OUTPUT_CODECS[".mp4"]["video"] == "libx264"


@pytest.mark.parametrize(
    ("suffix", "video"),
    [
        (".mp4", "libx264"),
        (".mov", "libx264"),
        (".mkv", "libx264"),
        (".webm", "libvpx-vp9"),
    ],
)
def test_pick_encoder_default_by_extension(suffix: str, video: str) -> None:
    """Без явного кодека берётся кодек контейнера (FR-20)."""
    assert encoders.pick_encoder(Path(f"out{suffix}"), None) == video


def test_pick_encoder_rejects_unknown_extension() -> None:
    """Расширение вне `OUTPUT_CODECS` отклоняется с префиксом `output` (FR-20)."""
    with pytest.raises(VideoTimerError, match=r"^output: "):
        encoders.pick_encoder(Path("out.avi"), None)


def test_a6_incompatible_codec_rejected_without_ffmpeg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A6: `libx264` для `.webm` отклоняется, ffmpeg не опрашивается (FR-21).

    Проверка совместимости чистая и идёт раньше проверки доступности кодеков,
    поэтому `available_encoders()` при несовместимой паре не вызывается — это
    и есть «ffmpeg не запускался».
    """

    def _boom() -> set[str]:
        raise AssertionError("available_encoders не должен вызываться")

    monkeypatch.setattr(encoders, "available_encoders", _boom)

    with pytest.raises(VideoTimerError, match=r"^encoder: "):
        encoders.pick_encoder(Path("out.webm"), "libx264")


def test_requested_codec_wins_when_compatible_and_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Явный кодек возвращается, если он совместим и есть в сборке (FR-21, FR-22)."""
    monkeypatch.setattr(encoders, "available_encoders", lambda: {"libvpx-vp9"})

    assert encoders.pick_encoder(Path("out.webm"), "libvpx-vp9") == "libvpx-vp9"


def test_requested_codec_missing_from_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Совместимый кодек, которого нет в сборке, отклоняется (FR-22)."""
    monkeypatch.setattr(encoders, "available_encoders", lambda: set())

    with pytest.raises(VideoTimerError, match=r"^encoder: "):
        encoders.pick_encoder(Path("out.mp4"), "libx265")


def test_available_encoders_lists_video_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`available_encoders()` разбирает вывод `ffmpeg -encoders` (FR-22).

    Строки-заголовки и аудиокодеки не попадают в результат: берутся только
    имена видео-кодеков.
    """
    stdout = (
        "Encoders:\n"
        " V..... = Video\n"
        " A..... = Audio\n"
        " ------\n"
        " V....D libx264           libx264 H.264\n"
        " A....D aac               AAC\n"
        " V....D libvpx-vp9        libvpx VP9\n"
    )
    monkeypatch.setattr(encoders.osutil, "find_ffmpeg", lambda: Path("/usr/bin/ffmpeg"))
    monkeypatch.setattr(
        encoders.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, stdout, ""),
    )
    monkeypatch.setattr(encoders, "_ENCODERS_CACHE", None)

    assert encoders.available_encoders() == {"libx264", "libvpx-vp9"}


def test_available_encoders_without_ffmpeg(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Без ffmpeg список кодеков получить нельзя — понятная ошибка (FR-55)."""
    monkeypatch.setattr(encoders.osutil, "find_ffmpeg", lambda: None)
    monkeypatch.setattr(encoders, "_ENCODERS_CACHE", None)

    with pytest.raises(VideoTimerError, match=r"^ffmpeg: "):
        encoders.available_encoders()


def _probe_video_codec(ffmpeg: str, path: Path) -> str | None:
    """Узнать имя кодека видео готового файла через ffprobe.

    Args:
        ffmpeg: путь к ffmpeg; рядом ищем ffprobe тем же способом.
        path: путь к готовому ролику.

    Returns:
        Имя кодека, например ``vp9``, или ``None``, если ffprobe недоступен.

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
            "stream=codec_name",
            "-of",
            "csv=p=0",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    return finished.stdout.strip() or None


@INTEGRATION
def test_a5_webm_output_is_vp9(tmp_path: Path) -> None:
    """A5: вывод в `.webm` — играбельный файл с кодеком vp9."""
    ffmpeg, _font = ffmpeg_or_skip()
    if "libvpx-vp9" not in encoders.available_encoders():
        pytest.skip("в сборке ffmpeg нет libvpx-vp9")

    cfg = TimerConfig(
        output=tmp_path / "a5.webm",
        duration=2.0,
        resolution="320x240",
        font_size=48,
    )
    cfg.validate()
    assert render(cfg).output.is_file()

    codec = _probe_video_codec(ffmpeg, cfg.output)
    if codec is None:
        pytest.skip("ffprobe не найден")
    assert codec == "vp9"
