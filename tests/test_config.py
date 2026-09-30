"""Тесты проверки конфигурации.

Основной сценарий — A7: `font-size 0` должен дать ошибку «font-size: …»
до запуска ffmpeg. Остальные проверки берутся из таблицы правил
`TimerConfig.validate()` (`SPEC.md` 7.1, `specs/v0.1.md`).

Часть критерия A7 про код возврата CLI (день 03.10) и подсветку поля в GUI
(день 05.10), а `test_output_parent_dir_created` — про рендер (день 02.10).
Эти тесты оставлены красными намеренно, с указанием дня в docstring.
"""

from __future__ import annotations

from dataclasses import MISSING, fields, replace
from pathlib import Path

import pytest

from video_timer.config import TimerConfig, VideoTimerError


def test_a7_font_size_zero_rejected(base_cfg: TimerConfig) -> None:
    """A7: `font-size 0` отклоняется с сообщением вида «font-size: …»."""
    cfg = replace(base_cfg, font_size=0)

    with pytest.raises(VideoTimerError) as excinfo:
        cfg.validate()

    assert str(excinfo.value).startswith("font-size: ")


def test_a7_gui_highlights_font_size_field(base_cfg: TimerConfig) -> None:
    """A7: сообщение GUI подсвечивает поле размера шрифта.

    Часть критерия A7 на день 05.10: нужны `FIELD_TO_WIDGET`, `ParamsPanel`
    и `_highlight_field`. Сегодня закрывается только сообщение `validate()`.
    """
    pytest.fail("не реализовано: A7 — подсветка поля font-size в GUI (день 05.10)")


def test_valid_config_passes(base_cfg: TimerConfig) -> None:
    """Корректная конфигурация не вызывает исключений."""
    base_cfg.validate()


def test_validate_raises_video_timer_error(base_cfg: TimerConfig) -> None:
    """`validate()` поднимает `VideoTimerError`, а не `ValueError` (FR-42)."""
    cfg = replace(base_cfg, font_size=0)

    with pytest.raises(VideoTimerError):
        cfg.validate()


def test_countdown_seconds_must_be_positive(base_cfg: TimerConfig) -> None:
    """`countdown-seconds` <= 0 при `mode=countdown` отклоняется (FR-02)."""
    cfg = replace(base_cfg, mode="countdown", countdown_seconds=0.0, duration=None)

    with pytest.raises(VideoTimerError, match=r"^countdown-seconds: "):
        cfg.validate()


def test_duration_required_for_stopwatch_on_color(base_cfg: TimerConfig) -> None:
    """Секундомер на сплошном цвете требует `duration` (FR-12)."""
    cfg = replace(base_cfg, duration=None)

    with pytest.raises(VideoTimerError, match=r"^duration: "):
        cfg.validate()


def test_duration_not_required_for_countdown_on_color(base_cfg: TimerConfig) -> None:
    """Для отсчёта длительность = N + hold, `duration` задавать не нужно (FR-12)."""
    cfg = replace(
        base_cfg,
        mode="countdown",
        countdown_seconds=10.0,
        hold_seconds=5.0,
        duration=None,
    )

    cfg.validate()


def test_hold_seconds_non_negative(base_cfg: TimerConfig) -> None:
    """`hold-seconds` < 0 отклоняется (FR-03)."""
    cfg = replace(base_cfg, hold_seconds=-1.0)

    with pytest.raises(VideoTimerError, match=r"^hold-seconds: "):
        cfg.validate()


@pytest.mark.parametrize("font_size", [0, 7, 501])
def test_font_size_bounds(base_cfg: TimerConfig, font_size: int) -> None:
    """Размер шрифта вне диапазона 8…500 отклоняется (FR-06)."""
    cfg = replace(base_cfg, font_size=font_size)

    with pytest.raises(VideoTimerError, match=r"^font-size: "):
        cfg.validate()


@pytest.mark.parametrize("font_size", [8, 64, 500])
def test_font_size_bounds_accepts_edges(base_cfg: TimerConfig, font_size: int) -> None:
    """Границы диапазона 8…500 допустимы (FR-06)."""
    replace(base_cfg, font_size=font_size).validate()


@pytest.mark.parametrize("fps", [0, 121])
def test_fps_bounds(base_cfg: TimerConfig, fps: int) -> None:
    """Частота кадров вне диапазона 1…120 отклоняется (FR-13)."""
    cfg = replace(base_cfg, fps=fps)

    with pytest.raises(VideoTimerError, match=r"^fps: "):
        cfg.validate()


@pytest.mark.parametrize("suffix", [".mov", ".webm", ".mkv"])
def test_output_extension_must_be_mp4(base_cfg: TimerConfig, suffix: str) -> None:
    """В v0.1 вывод с другим расширением отклоняется (FR-20)."""
    cfg = replace(base_cfg, output=base_cfg.output.with_suffix(suffix))

    with pytest.raises(VideoTimerError, match=r"^output: "):
        cfg.validate()


def test_output_parent_dir_created(base_cfg: TimerConfig, tmp_path: Path) -> None:
    """Отсутствующая папка вывода создаётся или даёт понятную ошибку.

    Папку результата создаёт `renderer` (день 02.10); `validate()` работает
    без побочных эффектов, поэтому тест закрывается вместе с рендером.
    """
    pytest.fail("не реализовано: FR-41 — понятная ошибка для output (день 02.10)")


def test_background_must_exist(base_cfg: TimerConfig) -> None:
    """Несуществующий файл фона отклоняется (FR-10)."""
    cfg = replace(base_cfg, background=base_cfg.output.parent / "нет-такого.mp4")

    with pytest.raises(VideoTimerError, match=r"^background: "):
        cfg.validate()


def test_background_extension_must_be_video(
    base_cfg: TimerConfig, tmp_path: Path
) -> None:
    """Файл фона с неподдерживаемым расширением отклоняется (FR-10)."""
    not_video = tmp_path / "картинка.txt"
    not_video.write_text("не видео", encoding="utf-8")
    cfg = replace(base_cfg, background=not_video)

    with pytest.raises(VideoTimerError, match=r"^background: "):
        cfg.validate()


@pytest.mark.parametrize("color", ["black", "white", "#fff", "#ff8800"])
def test_colors_accept_hex_and_whitelist(base_cfg: TimerConfig, color: str) -> None:
    """Цвета принимаются как `#rgb`, `#rrggbb` или имя из списка (FR-06)."""
    replace(base_cfg, bg_color=color, color=color, hold_color=color).validate()


@pytest.mark.parametrize(
    ("field", "cli_name"),
    [("bg_color", "bg-color"), ("color", "color"), ("hold_color", "hold-color")],
)
def test_colors_reject_garbage(
    base_cfg: TimerConfig, field: str, cli_name: str
) -> None:
    """Непонятный цвет отклоняется с именем поля в формате CLI (FR-41)."""
    cfg = replace(base_cfg, **{field: "не_цвет"})

    with pytest.raises(VideoTimerError, match=rf"^{cli_name}: "):
        cfg.validate()


def test_position_must_be_known(base_cfg: TimerConfig) -> None:
    """Позиция вне списка `POSITIONS` отклоняется (FR-05)."""
    cfg = replace(base_cfg, position="middle")

    with pytest.raises(VideoTimerError, match=r"^position: "):
        cfg.validate()


def test_known_total_duration_countdown(base_cfg: TimerConfig) -> None:
    """Для отсчёта на цвете длительность = N + hold (FR-12)."""
    cfg = replace(
        base_cfg,
        mode="countdown",
        countdown_seconds=10.0,
        hold_seconds=5.0,
        duration=None,
    )

    assert cfg.known_total_duration() == 15.0


def test_known_total_duration_stopwatch_color(base_cfg: TimerConfig) -> None:
    """Для секундомера на цвете длительность = `duration` (FR-12)."""
    assert base_cfg.known_total_duration() == 8.0


def test_known_total_duration_video_is_none(
    base_cfg: TimerConfig, tmp_path: Path
) -> None:
    """Длина видео-фона без `duration` известна только после ffprobe (FR-11)."""
    video = tmp_path / "фон.mp4"
    video.write_bytes(b"\x00")
    cfg = replace(base_cfg, background=video, duration=None)

    assert cfg.known_total_duration() is None


def test_resolved_encoder_is_libx264(base_cfg: TimerConfig) -> None:
    """Для `.mp4` без явного кодек выбирается libx264 (FR-20)."""
    assert base_cfg.resolved_encoder() == "libx264"


def test_error_message_has_field_prefix(base_cfg: TimerConfig) -> None:
    """Текст ошибки начинается с имени поля в формате CLI (FR-41)."""
    cfg = replace(base_cfg, hold_seconds=-1.0)

    with pytest.raises(VideoTimerError) as excinfo:
        cfg.validate()

    message = str(excinfo.value)
    prefix = message.split(":", 1)[0]
    assert prefix == "hold-seconds"
    assert message.split(":", 1)[1].strip()


def test_no_traceback_in_user_message(base_cfg: TimerConfig) -> None:
    """Пользователю не показывается трейсбек (FR-42)."""
    cfg = replace(base_cfg, font_size=0)

    with pytest.raises(VideoTimerError) as excinfo:
        cfg.validate()

    message = str(excinfo.value)
    assert "Traceback" not in message
    assert 'File "' not in message
    assert message.count("\n") == 0


def test_validate_reports_first_error_only(base_cfg: TimerConfig) -> None:
    """При нескольких ошибках сообщается о первой по порядку проверок (FR-41)."""
    cfg = replace(base_cfg, duration=0.0, font_size=0)

    with pytest.raises(VideoTimerError, match=r"^duration: "):
        cfg.validate()


def test_timer_config_fields_match_spec() -> None:
    """Состав полей и значения по умолчанию совпадают с SPEC 7.1."""
    names = tuple(f.name for f in fields(TimerConfig))

    assert names == (
        "output",
        "background",
        "bg_color",
        "mode",
        "countdown_seconds",
        "duration",
        "fmt",
        "position",
        "font",
        "font_size",
        "color",
        "hold_seconds",
        "hold_color",
        "bg_style",
        "resolution",
        "fit",
        "fps",
        "encoder",
        "crf",
        "preset",
    )

    defaults = {
        f.name: f.default for f in fields(TimerConfig) if f.default is not MISSING
    }
    assert defaults == {
        "background": None,
        "bg_color": "black",
        "mode": "stopwatch",
        "countdown_seconds": 60.0,
        "duration": None,
        "fmt": "mmss",
        "position": "br",
        "font": None,
        "font_size": 64,
        "color": "white",
        "hold_seconds": 5.0,
        "hold_color": "#e6362c",
        "bg_style": "shadow",
        "resolution": None,
        "fit": "contain",
        "fps": 30,
        "encoder": None,
        "crf": 18,
        "preset": "medium",
    }


def test_video_timer_error_is_runtime_error() -> None:
    """`VideoTimerError` наследуется от `RuntimeError` (SPEC 7.1)."""
    assert issubclass(VideoTimerError, RuntimeError)