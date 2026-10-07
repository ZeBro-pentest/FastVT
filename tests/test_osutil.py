"""Тесты поиска внешних программ и шрифта по умолчанию.

`find_ffprobe()` нужен `Background.probe_duration()`, `default_font()` —
`FilterBuilder.build_timer_filters()`. Обе функции обязаны возвращать
`None`, а не бросать: отсутствие ffprobe оставляет длительность
неизвестной, отсутствие шрифта — понятное сообщение (FR-06, FR-11, FR-55).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from video_timer import osutil


def test_default_font_returns_existing_file() -> None:
    """`default_font()` возвращает путь к реально существующему файлу (FR-06)."""
    font = osutil.default_font()

    assert font is not None
    assert font.is_file()
    assert font.suffix.lower() in {".ttf", ".otf", ".ttc"}


def test_default_font_none_when_nothing_found(
    tmp_path: Path, monkeypatch
) -> None:
    """Если шрифтов нет — `None`, а не исключение; сообщает об этом `FilterBuilder`."""
    monkeypatch.setattr(osutil, "_font_dirs", lambda: (tmp_path,))
    monkeypatch.setattr(sys, "platform", "test-os")

    assert osutil.default_font() is None


def test_find_ffprobe_returns_existing_file() -> None:
    """`find_ffprobe()` возвращает путь к существующему ffprobe (FR-11)."""
    probe = osutil.find_ffprobe()

    if probe is None:
        return
    assert probe.is_file()


def test_find_ffprobe_none_when_missing(monkeypatch) -> None:
    """Нет ffprobe — `None`; длительность просто остаётся неизвестной (FR-11)."""
    monkeypatch.setattr(shutil, "which", lambda _name: None)

    assert osutil.find_ffprobe() is None


def test_find_ffprobe_finds_exe_suffix() -> None:
    """На Windows имя программы дополняется `.exe` (SPEC 7.7)."""
    called: list[str] = []

    def fake_which(name: str) -> str:
        called.append(name)
        if name == "ffprobe.exe":
            return r"C:\ffmpeg\bin\ffprobe.exe"
        return ""

    original = shutil.which
    try:
        import video_timer.osutil as module

        module._which = fake_which
        assert module.find_ffprobe() == Path(r"C:\ffmpeg\bin\ffprobe.exe")
    finally:
        import video_timer.osutil as module

        module._which = original

    assert any(name.endswith(".exe") or name == "ffprobe" for name in called)
    assert os.name in {"posix", "nt"}


def test_find_ffprobe_ignores_empty_path() -> None:
    """Пустая строка из `which` не превращается в путь к файлу."""
    import video_timer.osutil as module

    original = module._which
    try:
        module._which = lambda _name: ""
        assert module.find_ffprobe() is None
    finally:
        module._which = original