"""Тесты GUI и критерия A11: окно, кнопка рендера, поток, поиск ffmpeg.

Окно должно открыться даже без ffmpeg, показать понятное сообщение с
инструкцией, а кнопка «Рендерить» — не запускать рендер и объяснить
причину (A11, FR-55). Рендер идёт в отдельном потоке через очередь событий
(NFR-05), поэтому тесты подменяют `renderer.render` фейком и не зовут
настоящий ffmpeg.

Тесты с настоящим окном используют фикстуру `tk_root`: если дисплея нет,
они пропускаются, а не падают.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import pytest

from video_timer import osutil
from video_timer.config import TimerConfig, VideoTimerError
from video_timer.gui import panels
from video_timer.gui.app import VideoTimerApp
from video_timer.gui.panels import (
    FIELD_TO_WIDGET,
    ParamsPanel,
    RenderPanel,
)
from video_timer.gui.worker import RenderWorker
from video_timer.renderer import RenderResult


VALIDATED_FIELDS = {
    "output",
    "background",
    "bg_color",
    "mode",
    "countdown-seconds",
    "duration",
    "position",
    "font-size",
    "color",
    "hold-seconds",
    "hold-color",
    "fps",
}
"""Поля, проверяемые `TimerConfig.validate()` в v0.1 (FR-41)."""


def _make_renderer(
    *,
    progress: list[tuple[float, float | None]] | None = None,
    result: RenderResult | None = None,
    error: VideoTimerError | None = None,
    delay: float = 0.0,
) -> Callable[[TimerConfig, object | None], RenderResult]:
    """Вернуть фейк `renderer.render` для тестов GUI и потока.

    Спека: FR-51, NFR-05. Версия: v0.1.

    Args:
        progress: список пар `(доля, всего_секунд)`, который фейк публикует
            через `on_progress`.
        result: результат, который вернуть на успехе.
        error: ошибка, которую поднять вместо результата.
        delay: долгий «рендер» для тестов неблокирующего GUI.

    Returns:
        Функция с сигнатурой `renderer.render(cfg, on_progress)`.
    """
    def render(
        cfg: TimerConfig, on_progress: Callable[[float, float | None], None] | None = None
    ) -> RenderResult:
        time.sleep(delay)
        for fraction, total in progress or []:
            if on_progress is not None:
                on_progress(fraction, total)
        if error is not None:
            raise error
        assert result is not None
        return result

    return render


def _pump(
    root: object, app: VideoTimerApp, condition: Callable[[], bool], timeout: float = 3.0
) -> bool:
    """Довести главный цикл окна до наступления условия.

    Спека: FR-51, NFR-05. Версия: v0.1.

    Вместо `root.mainloop()` тест сам даёт окну обновить виджеты и обработать
    события из очереди, пока не сработает `condition` или не выйдет `timeout`.

    Args:
        root: корневое окно Tkinter.
        app: приложение, чей опрос событий вызывается каждую итерацию.
        condition: предикат «тест закончен».
        timeout: сколько секунд ждать события.

    Returns:
        True, если условие наступило; False — если время вышло.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root.update()  # type: ignore[attr-defined]
        app._poll_events()
        if condition():
            return True
        time.sleep(0.02)
    return False


def _no_ffmpeg(monkeypatch: pytest.MonkeyPatch) -> None:
    """Подменить поиск ffmpeg на несуществующий (критерий A11)."""
    monkeypatch.setattr(osutil, "find_ffmpeg", lambda: None)


def test_a11_find_ffmpeg_returns_none_when_absent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A11: без ffmpeg в `PATH` и в папке сборки поиск даёт `None`."""
    monkeypatch.setattr(osutil, "_which", lambda name: "")
    monkeypatch.setattr(osutil, "_bundle_dir", lambda: tmp_path)

    assert osutil.find_ffmpeg() is None


def test_a11_window_opens_without_ffmpeg(
    tk_root: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A11: окно создаётся, даже если ffmpeg не найден (FR-55)."""
    _no_ffmpeg(monkeypatch)

    app = VideoTimerApp(tk_root)  # type: ignore[arg-type]

    assert app._ffmpeg is None


def test_a11_message_contains_instruction(
    tk_root: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A11: в сообщении есть инструкция, что делать дальше (FR-55)."""
    _no_ffmpeg(monkeypatch)
    app = VideoTimerApp(tk_root)  # type: ignore[arg-type]

    app.on_render()
    status = app.render_panel.status_label.cget("text")

    assert "ffmpeg" in status.lower()
    assert "установ" in status.lower()


def test_a11_render_button_does_not_start_render(
    tk_root: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A11: нажатие «Рендерить» не запускает ffmpeg и объясняет причину."""
    _no_ffmpeg(monkeypatch)
    calls: list[object] = []
    monkeypatch.setattr(
        "video_timer.gui.worker.renderer.render", lambda *args, **kwargs: calls.append(args)
    )
    app = VideoTimerApp(tk_root)  # type: ignore[arg-type]

    app.on_render()

    assert calls == []  # ffmpeg не запускался
    assert app.render_panel.status_label.cget("text") != ""
    assert "ffmpeg" in app.render_panel.status_label.cget("text").lower()
    assert not app.worker._running


def test_a11_no_traceback_shown(
    tk_root: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A11: вместо трейсбека в статусной строке текст на русском (FR-42)."""
    _no_ffmpeg(monkeypatch)
    app = VideoTimerApp(tk_root)  # type: ignore[arg-type]

    app.on_render()

    assert "Traceback" not in app.render_panel.status_label.cget("text")
    assert app.render_panel.status_label.cget("text") != ""


def test_app_can_be_imported_without_display() -> None:
    """Импорт `video_timer.gui.app` не создаёт окон и не требует дисплея."""
    import video_timer.gui.app as app_module

    assert callable(app_module.main)


def test_render_starts_when_ffmpeg_present(
    tk_root: object, monkeypatch: pytest.MonkeyPatch, base_cfg: TimerConfig
) -> None:
    """С ffmpeg на месте кнопка «Рендерить» запускает рендер (контроль A11)."""
    monkeypatch.setattr(osutil, "find_ffmpeg", lambda: Path("/usr/bin/ffmpeg"))
    result = RenderResult(base_cfg.output, 8.0, "ffmpeg: ok")
    renderer = _make_renderer(result=result)
    monkeypatch.setattr("video_timer.gui.worker.renderer.render", renderer)
    app = VideoTimerApp(tk_root)  # type: ignore[arg-type]
    app.params._output_var.set(str(base_cfg.output))
    app.params._duration_var.set("8")

    app.on_render()
    ok = _pump(
        tk_root,  # type: ignore[arg-type]
        app,
        lambda: app.render_panel.status_label.cget("text").startswith("Готово"),
    )

    assert ok
    assert app.render_panel.status_label.cget("text").endswith(str(base_cfg.output))


def test_ffmpeg_found_next_to_application(tmp_path: Path) -> None:
    """A10: ffmpeg в папке сборки находится раньше `PATH` (v0.3)."""
    pytest.fail("не реализовано: A10 — поиск ffmpeg рядом с приложением (v0.3)")


def test_find_ffprobe_returns_path_or_none() -> None:
    """Поиск ffprobe даёт путь или `None`, а не исключение (FR-11)."""
    found = osutil.find_ffprobe()

    assert found is None or found.is_file()


def test_default_font_returns_path_or_none() -> None:
    """Поиск шрифта по умолчанию даёт путь или `None` (FR-06)."""
    font = osutil.default_font()

    assert font is None or font.is_file()


def test_open_folder_is_cross_platform(tmp_path: Path) -> None:
    """Открытие папки работает на всех трёх системах (v0.2, FR-54)."""
    pytest.fail("не реализовано: FR-54 — open_folder() кроссплатформенно (v0.2)")


def test_app_class_exposes_handlers() -> None:
    """У приложения есть обработчики рендера, оценки и отмены (SPEC 7.9)."""
    for name in ("build_config", "on_render", "on_estimate", "on_cancel"):
        assert callable(getattr(VideoTimerApp, name))


def test_build_config_reads_widget_values(
    tk_root: object, base_cfg: TimerConfig
) -> None:
    """`build_config()` собирает конфигурацию из значений полей (FR-40)."""
    app = VideoTimerApp(tk_root)  # type: ignore[arg-type]
    app.params._output_var.set(str(base_cfg.output))
    app.params._duration_var.set("8")

    assert app.build_config() == base_cfg


def test_field_to_widget_covers_validated_fields(
    tk_root: object,
) -> None:
    """`FIELD_TO_WIDGET` содержит строку на каждое проверяемое поле (FR-41)."""
    panel = ParamsPanel(tk_root)  # type: ignore[arg-type]

    assert set(FIELD_TO_WIDGET) == VALIDATED_FIELDS
    for widget_name in FIELD_TO_WIDGET.values():
        assert hasattr(panel, widget_name)


def test_render_worker_poll_returns_events() -> None:
    """`RenderWorker.poll()` отдаёт список событий, а не блокирует (NFR-05)."""
    worker = RenderWorker()

    assert worker.poll() == []  # пустая очередь — пустой список
    assert not worker._running


def test_render_worker_does_not_touch_tk() -> None:
    """Поток рендера не обращается к виджетам: только очередь событий (NFR-05)."""
    import video_timer.gui.worker as worker_module

    source = Path(worker_module.__file__).read_text(encoding="utf-8")
    assert "tkinter" not in source


def test_gui_does_not_block_during_render(
    base_cfg: TimerConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Рендер идёт в отдельном потоке, окно остаётся отзывчивым (NFR-05)."""
    renderer = _make_renderer(
        result=RenderResult(base_cfg.output, 8.0, ""), delay=0.5
    )
    monkeypatch.setattr("video_timer.gui.worker.renderer.render", renderer)
    worker = RenderWorker()

    worker.start(base_cfg)
    started = time.monotonic()
    while time.monotonic() - started < 0.2:
        assert worker.poll() == []  # пока рендер идёт — очередь пуста
        time.sleep(0.02)
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        events = worker.poll()
        if events:
            assert events[0].kind == "done"
            break
        time.sleep(0.05)
    else:
        pytest.fail("поток рендера не отдал событие done вовремя")


def test_osutil_exposes_four_functions() -> None:
    """Модуль `osutil` объявляет четыре функции вместо `platform.py` (SPEC 7.7)."""
    for name in ("find_ffmpeg", "find_ffprobe", "default_font", "open_folder"):
        assert callable(getattr(osutil, name))


def test_progress_bar_updates_on_render(
    tk_root: object, monkeypatch: pytest.MonkeyPatch, base_cfg: TimerConfig
) -> None:
    """Прогресс-бар двигается по событиям `progress` из потока (FR-51)."""
    monkeypatch.setattr(osutil, "find_ffmpeg", lambda: Path("/usr/bin/ffmpeg"))
    monkeypatch.setattr(
        "video_timer.gui.worker.renderer.render",
        _make_renderer(
            progress=[(0.5, 8.0)], result=RenderResult(base_cfg.output, 8.0, "")
        ),
    )
    app = VideoTimerApp(tk_root)  # type: ignore[arg-type]
    app.params._output_var.set(str(base_cfg.output))
    app.params._duration_var.set("8")

    app.on_render()
    ok = _pump(
        tk_root,  # type: ignore[arg-type]
        app,
        lambda: app.render_panel.progress_bar["value"] > 0,
    )

    assert ok
    assert app.render_panel.progress_bar["value"] == 50


def test_render_panel_has_render_button(tk_root: object) -> None:
    """В нижней панели есть кнопка «Рендерить» (FR-51)."""
    panel = RenderPanel(tk_root)  # type: ignore[arg-type]

    assert "Рендерить" in panel.render_button["text"]


def test_params_panel_has_v01_fields(tk_root: object) -> None:
    """Левая панель содержит поля версии v0.1 (FR-51)."""
    panel = ParamsPanel(tk_root)  # type: ignore[arg-type]

    for field in VALIDATED_FIELDS:
        assert hasattr(panel, FIELD_TO_WIDGET[field])
    assert hasattr(panels, "FIELD_TO_WIDGET")


def test_ffmpeg_binary_is_available_on_path() -> None:
    """Контроль окружения: ffmpeg установлен (пропуск теста, если нет)."""
    if osutil.find_ffmpeg() is None:
        pytest.skip("ffmpeg не найден в тестовой среде")