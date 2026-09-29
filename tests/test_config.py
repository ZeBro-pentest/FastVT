"""Тесты проверки конфигурации.

Основной сценарий — A7: `font-size 0` должен дать ошибку «font-size: …»
до запуска ffmpeg. Остальные проверки берутся из таблицы правил
`TimerConfig.validate()` (`SPEC.md` 7.1, `specs/v0.1.md`).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from video_timer.config import TimerConfig, VideoTimerError


def test_a7_font_size_zero_rejected(base_cfg: TimerConfig) -> None:
    """A7: `font-size 0` отклоняется с сообщением вида «font-size: …»."""
    pytest.fail("не реализовано: A7 — font-size 0 отклоняется validate()")


def test_a7_gui_highlights_font_size_field(base_cfg: TimerConfig) -> None:
    """A7: сообщение GUI подсвечивает поле размера шрифта."""
    pytest.fail("не реализовано: A7 — подсветка поля font-size в GUI")


def test_valid_config_passes(base_cfg: TimerConfig) -> None:
    """Корректная конфигурация не вызывает исключений."""
    pytest.fail("не реализовано: FR-40 — валидный TimerConfig проходит validate()")


def test_validate_raises_video_timer_error(base_cfg: TimerConfig) -> None:
    """`validate()` поднимает `VideoTimerError`, а не `ValueError` (FR-42)."""
    with pytest.raises(VideoTimerError):
        pytest.fail("не реализовано: FR-42 — тип исключения validate()")


def test_countdown_seconds_must_be_positive(base_cfg: TimerConfig) -> None:
    """`countdown-seconds` <= 0 при `mode=countdown` отклоняется (FR-02)."""
    pytest.fail("не реализовано: FR-02 — countdown-seconds должен быть > 0")


def test_duration_required_for_stopwatch_on_color(base_cfg: TimerConfig) -> None:
    """Секундомер на сплошном цвете требует `duration` (FR-12)."""
    pytest.fail("не реализовано: FR-12 — duration обязателен для stopwatch без видео")


def test_duration_not_required_for_countdown_on_color(base_cfg: TimerConfig) -> None:
    """Для отсчёта длительность = N + hold, `duration` задавать не нужно (FR-12)."""
    pytest.fail("не реализовано: FR-12 — duration необязателен для countdown")


def test_hold_seconds_non_negative(base_cfg: TimerConfig) -> None:
    """`hold-seconds` < 0 отклоняется (FR-03)."""
    pytest.fail("не реализовано: FR-03 — hold-seconds должен быть >= 0")


def test_font_size_bounds(base_cfg: TimerConfig) -> None:
    """Размер шрифта вне диапазона 8…500 отклоняется (FR-06)."""
    pytest.fail("не реализовано: FR-06 — font-size в диапазоне 8…500")


def test_fps_bounds(base_cfg: TimerConfig) -> None:
    """Частота кадров вне диапазона 1…120 отклоняется (FR-13)."""
    pytest.fail("не реализовано: FR-13 — fps в диапазоне 1…120")


def test_output_extension_must_be_mp4(base_cfg: TimerConfig) -> None:
    """В v0.1 вывод с другим расширением отклоняется (FR-20)."""
    pytest.fail("не реализовано: FR-20 — в v0.1 допустимо только .mp4")


def test_background_must_exist(base_cfg: TimerConfig) -> None:
    """Несуществующий файл фона отклоняется (FR-10)."""
    pytest.fail("не реализовано: FR-10 — background должен существовать")


def test_background_extension_must_be_video(base_cfg: TimerConfig) -> None:
    """Файл фона с неподдерживаемым расширением отклоняется (FR-10)."""
    pytest.fail("не реализовано: FR-10 — background должен быть видеофайлом")


def test_colors_accept_hex_and_whitelist(base_cfg: TimerConfig) -> None:
    """Цвета принимаются как `#rgb`, `#rrggbb` или имя из списка (FR-06)."""
    pytest.fail("не реализовано: FR-06 — проверка bg_color, color, hold_color")


def test_position_must_be_known(base_cfg: TimerConfig) -> None:
    """Позиция вне списка `POSITIONS` отклоняется (FR-05)."""
    pytest.fail("не реализовано: FR-05 — position из POSITIONS")


def test_known_total_duration_countdown(base_cfg: TimerConfig) -> None:
    """Для отсчёта на цвете длительность = N + hold (FR-12)."""
    pytest.fail("не реализовано: FR-12 — known_total_duration для countdown")


def test_known_total_duration_video_is_none(base_cfg: TimerConfig) -> None:
    """Для видео-фона без `duration` длина известна только после ffprobe (FR-11)."""
    pytest.fail("не реализовано: FR-11 — known_total_duration для видео-фона")


def test_resolved_encoder_is_libx264(base_cfg: TimerConfig) -> None:
    """Для `.mp4` без явного кодек выбирается libx264 (FR-20)."""
    pytest.fail("не реализовано: FR-20 — resolved_encoder для .mp4")


def test_error_message_has_field_prefix(base_cfg: TimerConfig) -> None:
    """Текст ошибки начинается с имени поля в формате CLI (FR-41)."""
    pytest.fail("не реализовано: FR-41 — префикс «поле: » в VideoTimerError")


def test_no_traceback_in_user_message(base_cfg: TimerConfig) -> None:
    """Пользователю не показывается трейсбек (FR-42)."""
    pytest.fail("не реализовано: FR-42 — в сообщении нет трейсбека")


def test_validate_reports_first_error_only(base_cfg: TimerConfig) -> None:
    """При нескольких ошибках сообщается о первой по порядку проверок (FR-41)."""
    pytest.fail("не реализовано: FR-41 — подсветка только первого ошибочного поля")


def test_timer_config_fields_match_spec() -> None:
    """Состав полей и значения по умолчанию совпадают с SPEC 7.1."""
    pytest.fail("не реализовано: SPEC 7.1 — состав полей TimerConfig")


def test_video_timer_error_is_runtime_error() -> None:
    """`VideoTimerError` наследуется от `RuntimeError` (SPEC 7.1)."""
    pytest.fail("не реализовано: SPEC 7.1 — VideoTimerError(RuntimeError)")


def test_output_parent_dir_created(base_cfg: TimerConfig, tmp_path: Path) -> None:
    """Отсутствующая папка вывода создаётся или даёт понятную ошибку."""
    pytest.fail("не реализовано: FR-41 — понятная ошибка для output")
