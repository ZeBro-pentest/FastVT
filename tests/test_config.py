"""Тесты проверки конфигурации.

Основной сценарий — A7: `font-size 0` должен дать ошибку «font-size: …»
до запуска ffmpeg. Остальные проверки берутся из таблицы правил
`TimerConfig.validate()` (`SPEC.md` 7.1, `specs/v0.1.md`).

Часть критерия A7 про код возврата CLI (день 03.10) закрыта тестами CLI,
подсветка поля в GUI (день 06.10) — тестом `test_a7_gui_highlights_font_size_field`.
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


def test_a7_gui_highlights_font_size_field(
    tk_root: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A7: сообщение GUI подсвечивает поле размера шрифта.

    Часть критерия A7 на день 06.10: ошибка «font-size: …» из `validate()`
    подсвечивает виджет поля через `FIELD_TO_WIDGET`, а рендер не стартует.
    """
    import time

    import video_timer.gui.app as app_module
    from video_timer import osutil as osutil_module
    from video_timer.gui.panels import FIELD_ERROR_BG

    monkeypatch.setattr(osutil_module, "find_ffmpeg", lambda: Path("/usr/bin/ffmpeg"))

    def _no_ffmpeg(cfg: TimerConfig, on_progress=None) -> None:
        cfg.validate()
        pytest.fail("ffmpeg не должен запускаться при ошибке валидации")

    monkeypatch.setattr("video_timer.gui.worker.renderer.render", _no_ffmpeg)
    app = app_module.VideoTimerApp(tk_root)  # type: ignore[arg-type]
    app.params._output_var.set("out.mp4")
    app.params._duration_var.set("8")
    app.params._font_size_var.set("0")
    error_widget = getattr(app.params, app_module.FIELD_TO_WIDGET["font-size"])

    assert error_widget.cget("background") != FIELD_ERROR_BG
    app.on_render()

    deadline = time.monotonic() + 3.0
    while error_widget.cget("background") != FIELD_ERROR_BG:
        assert time.monotonic() < deadline, "событие error не пришло вовремя"
        tk_root.update()  # type: ignore[attr-defined]
        app._poll_events()
        time.sleep(0.02)

    assert app.render_panel.status_label.cget("text") != ""
    assert not app.worker._running


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


def test_non_numeric_duration_is_rejected(base_cfg: TimerConfig) -> None:
    """Нечисловое число отвечает «поле: должно быть числом» (FR-41).

    GUI передаёт в `TimerConfig` строки из полей окна, поэтому `validate()`
    должна превратить `"abc"` в понятную ошибку, а не в `TypeError`.
    """
    cfg = replace(base_cfg, duration="abc")

    with pytest.raises(VideoTimerError, match=r"^duration: должно быть числом$"):
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


def test_validate_does_not_create_output_dir(base_cfg: TimerConfig) -> None:
    """`validate()` не создаёт папку результата — это делает `renderer`.

    Спека: FR-41, NFR-01. Версия: v0.1.

    Проверка без побочных эффектов: если бы `validate()` создавал папку, то
    отказ конфигурации по другой причине оставлял бы на диске пустой каталог.
    Создание папки проверяет `tests/test_renderer.py::test_output_parent_dir_created`.

    Args:
        base_cfg: валидная конфигурация из фикстуры.
    """
    output = base_cfg.output.parent / "не-должно-появиться" / "out.mp4"
    cfg = replace(base_cfg, output=output, font_size=0)

    with pytest.raises(VideoTimerError, match=r"^font-size: "):
        cfg.validate()

    assert not output.parent.exists()


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