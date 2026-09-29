"""Тесты командного интерфейса.

Коды возврата (SPEC 7.8): 0 — успех, 1 — ошибка валидации или рендера,
2 — неверные аргументы. Сценарий A7 проверяется через CLI: код 1 и
сообщение с префиксом имени поля, ffmpeg при этом не запускался.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from video_timer.cli import build_parser, main


def test_a7_exit_code_1_on_font_size_zero(capsys: pytest.CaptureFixture) -> None:
    """A7: `font-size 0` даёт код возврата 1, а не 0 и не 2."""
    pytest.fail("не реализовано: A7 — код возврата 1 при font-size 0")


def test_a7_message_starts_with_field_name(capsys: pytest.CaptureFixture) -> None:
    """A7: в `stderr` есть сообщение, начинающееся с `font-size: `."""
    pytest.fail("не реализовано: A7 — сообщение начинается с «font-size: »")


def test_a7_no_traceback_in_output(capsys: pytest.CaptureFixture) -> None:
    """A7: в выводе нет трейсбека (FR-42)."""
    pytest.fail("не реализовано: FR-42 — CLI не печатает трейсбек")


def test_a7_ffmpeg_not_launched(monkeypatch: pytest.MonkeyPatch) -> None:
    """A7: ffmpeg не запускался — команда рендера не вызывалась вовсе."""
    pytest.fail("не реализовано: A7 — ffmpeg не запускается при ошибке валидации")


def test_spec_example_command_succeeds(tmp_path: Path) -> None:
    """Пример из `specs/v0.1.md` отсчитывает 10 с и завершается кодом 0."""
    pytest.fail("не реализовано: FR-50 — пример из спеки рендерит видео")


def test_success_returns_zero(tmp_path: Path) -> None:
    """Успешный рендер даёт код возврата 0 и печатает путь результата."""
    pytest.fail("не реализовано: FR-50 — код 0 при успешном рендере")


def test_render_error_returns_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ошибка рендера даёт код 1 и понятный текст без лога ffmpeg (FR-42)."""
    pytest.fail("не реализовано: FR-42 — код 1 при ошибке рендера")


def test_unknown_argument_returns_two() -> None:
    """Неизвестная опция даёт код 2 — это ошибка разбора, не валидации."""
    pytest.fail("не реализовано: SPEC 7.8 — код 2 при неверных аргументах")


def test_missing_output_option_returns_two() -> None:
    """Без обязательной `-o` argparse завершает работу с кодом 2."""
    pytest.fail("не реализовано: SPEC 7.8 — -o обязательна")


def test_help_returns_zero() -> None:
    """`--help` показывает справку на русском и завершает работу с кодом 0."""
    pytest.fail("не реализовано: FR-50 — русская справка --help")


def test_parser_option_names_match_config_fields() -> None:
    """Имя опции с дефисом соответствует полю конфигурации (FR-41)."""
    pytest.fail("не реализовано: FR-41 — имена опций совпадают с полями")


def test_parser_accepts_video_background(tmp_path: Path) -> None:
    """Опция `-b` принимает путь к видеофайлу (FR-10)."""
    pytest.fail("не реализовано: FR-10 — опция -b для видеофона")


def test_parser_rejects_bad_choice() -> None:
    """Недопустимый выбор для `--mode` отклоняется argparse (FR-01)."""
    pytest.fail("не реализовано: FR-01 — выбор mode ограничен двумя значениями")


def test_main_accepts_argv_list(tmp_path: Path) -> None:
    """`main(argv)` работает со списком аргументов без `sys.argv` (SPEC 7.8)."""
    pytest.fail("не реализовано: SPEC 7.8 — main(argv) без sys.argv")


def test_parser_is_reusable() -> None:
    """`build_parser()` создаёт новый парсер, а не общий изменяемый (SPEC 7.8)."""
    pytest.fail("не реализовано: SPEC 7.8 — build_parser() даёт независимый парсер")


def test_cli_reports_estimate_only() -> None:
    """Опция `--estimate-only` печатает оценку без кодирования (v0.2, A8)."""
    pytest.fail("не реализовано: A8 — --estimate-only без запуска кодирования")


def test_module_exports_entry_points() -> None:
    """Модуль объявляет `build_parser()`, `main()` и точку входа (SPEC 7.8)."""
    pytest.fail("не реализовано: SPEC 7.8 — состав интерфейса video_timer.cli")
