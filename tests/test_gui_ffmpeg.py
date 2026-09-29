"""Тест критерия A11: GUI без ffmpeg в системе.

Окно должно открыться, показать понятное сообщение с инструкцией, а кнопка
«Рендерить» — не запускать рендер и объяснить причину. Тест не создаёт
окно вслепую: если ffmpeg подменён на несуществующий путь, достаточно
проверить решение приложения, без запуска Tkinter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from video_timer import osutil
from video_timer.config import TimerConfig
from video_timer.gui.app import VideoTimerApp


def test_a11_find_ffmpeg_returns_none_when_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A11: без ffmpeg в `PATH` и в папке сборки поиск даёт `None`."""
    pytest.fail("не реализовано: A11 — find_ffmpeg() == None без ffmpeg")


def test_a11_window_opens_without_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    """A11: окно создаётся, даже если ffmpeg не найден (FR-55)."""
    pytest.fail("не реализовано: A11 — окно открывается без ffmpeg")


def test_a11_message_contains_instruction(monkeypatch: pytest.MonkeyPatch) -> None:
    """A11: в сообщении есть инструкция, что делать дальше (FR-55)."""
    pytest.fail("не реализовано: FR-55 — инструкция по установке ffmpeg")


def test_a11_render_button_does_not_start_render(
    monkeypatch: pytest.MonkeyPatch, base_cfg: TimerConfig
) -> None:
    """A11: нажатие «Рендерить» не запускает ffmpeg и объясняет причину."""
    pytest.fail("не реализовано: A11 — кнопка объясняет причину, а не падает")


def test_a11_no_traceback_shown(monkeypatch: pytest.MonkeyPatch) -> None:
    """A11: вместо трейсбека в статусной строке текст на русском (FR-42)."""
    pytest.fail("не реализовано: FR-42 — GUI не показывает трейсбек")


def test_app_can_be_imported_without_display() -> None:
    """Импорт `video_timer.gui.app` не создаёт окон и не требует дисплея."""
    pytest.fail("не реализовано: FR-55 — импорт gui.app без дисплея")


def test_render_starts_when_ffmpeg_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """С ffmpeg на месте кнопка «Рендерить» запускает рендер (контроль A11)."""
    pytest.fail("не реализовано: FR-51 — рендер запускается при наличии ffmpeg")


def test_ffmpeg_found_next_to_application(tmp_path: Path) -> None:
    """A10: ffmpeg в папке сборки находится раньше `PATH` (v0.3)."""
    pytest.fail("не реализовано: A10 — поиск ffmpeg рядом с приложением")


def test_find_ffprobe_returns_path_or_none() -> None:
    """Поиск ffprobe даёт путь или `None`, а не исключение (FR-11)."""
    pytest.fail("не реализовано: FR-11 — find_ffprobe() без исключений")


def test_default_font_returns_path_or_none() -> None:
    """Поиск шрифта по умолчанию даёт путь или `None` (FR-06)."""
    pytest.fail("не реализовано: FR-06 — default_font() без исключений")


def test_open_folder_is_cross_platform(tmp_path: Path) -> None:
    """Открытие папки работает на всех трёх системах (v0.2, FR-54)."""
    pytest.fail("не реализовано: FR-54 — open_folder() кроссплатформенно")


def test_app_class_exposes_handlers() -> None:
    """У приложения есть обработчики рендера, оценки и отмены (SPEC 7.9)."""
    pytest.fail("не реализовано: SPEC 7.9 — состав интерфейса VideoTimerApp")


def test_build_config_reads_widget_values(base_cfg: TimerConfig) -> None:
    """`build_config()` собирает конфигурацию из значений полей (FR-40)."""
    pytest.fail("не реализовано: FR-40 — VideoTimerApp.build_config()")


def test_field_to_widget_covers_validated_fields() -> None:
    """`FIELD_TO_WIDGET` содержит строку на каждое проверяемое поле (FR-41)."""
    pytest.fail("не реализовано: FR-41 — таблица FIELD_TO_WIDGET заполнена")


def test_render_worker_poll_returns_events() -> None:
    """`RenderWorker.poll()` отдаёт список событий, а не блокирует (NFR-05)."""
    pytest.fail("не реализовано: NFR-05 — poll() не блокирует")


def test_render_worker_does_not_touch_tk() -> None:
    """Поток рендера не обращается к виджетам: только очередь событий (NFR-05)."""
    pytest.fail("не реализовано: NFR-05 — поток не трогает виджеты")


def test_gui_does_not_block_during_render() -> None:
    """Рендер идёт в отдельном потоке, окно остаётся отзывчивым (NFR-05)."""
    pytest.fail("не реализовано: NFR-05 — рендер в отдельном потоке")


def test_osutil_exposes_four_functions() -> None:
    """Модуль `osutil` объявляет четыре функции вместо `platform.py` (SPEC 7.7)."""
    pytest.fail("не реализовано: SPEC 7.7 — состав интерфейса video_timer.osutil")


def test_progress_bar_updates_on_render(base_cfg: TimerConfig) -> None:
    """Прогресс-бар двигается по событиям `progress` из потока (FR-51)."""
    pytest.fail("не реализовано: FR-51 — прогресс-бар по событиям")


def test_render_panel_has_render_button() -> None:
    """В нижней панели есть кнопка «Рендерить» (FR-51)."""
    pytest.fail("не реализовано: FR-51 — кнопка «Рендерить» в RenderPanel")


def test_params_panel_has_v01_fields(base_cfg: TimerConfig) -> None:
    """Левая панель содержит поля версии v0.1 (FR-51)."""
    pytest.fail("не реализовано: FR-51 — поля v0.1 в ParamsPanel")


def test_ffmpeg_binary_is_available_on_path() -> None:
    """Контроль окружения: ffmpeg установлен (пропуск теста, если нет)."""
    pytest.fail("не реализовано: FR-55 — проверка наличия ffmpeg в тестовой среде")
