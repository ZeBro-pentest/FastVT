"""Главное окно приложения: сборка панелей, конфигурации и обработчики.

Модуль связывает виджеты (`panels`) и поток рендера (`worker`) с движком
(`renderer`, `estimate`, `osutil`). Логика GUI — только разбор полей,
показ ошибок и обновление прогресса; кодирование живёт в отдельном потоке,
чтобы окно не блокировалось (NFR-05).

Зависимости: `config`, `renderer`, `estimate`, `osutil`, `gui.panels`,
`gui.worker`. Движок не импортирует tkinter.

Окно не создаётся при импорте модуля — только при вызове `main()`, поэтому
`import video_timer.gui.app` безопасен без дисплея.
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

from video_timer import __version__, osutil
from video_timer.config import TimerConfig, VideoTimerError
from video_timer.gui.panels import (
    FIELD_ERROR_BG,
    FIELD_TO_WIDGET,
    ParamsPanel,
    RenderPanel,
)
from video_timer.gui.worker import RenderWorker


# since: v0.1 (FR-40, FR-41)
def _read_str(var: tk.StringVar, default: str) -> str:
    """Вернуть текст поля или значение по умолчанию при пустой строке.

    Args:
        var: переменная Tkinter поля.
        default: значение для пустого поля.

    Returns:
        Введённый текст без пробелов по краям или `default`.
    """
    return var.get().strip() or default


def _read_path(var: tk.StringVar) -> Path | None:
    """Вернуть путь из поля либо ``None``, если поле пустое.

    Args:
        var: переменная Tkinter поля пути.

    Returns:
        `Path` без проверки существования или ``None``.
    """
    text = var.get().strip()
    return Path(text) if text else None


def _read_number(var: tk.StringVar, default: int | float) -> int | float | str:
    """Разобрать число из поля окна либо сохранить строку для `validate()`.

    Спека: FR-41. Версия: v0.1.

    Пустое поле — значение по умолчанию. Неразборчивый текст остаётся
    строкой и попадает в `TimerConfig` как есть, где `validate()` ответит
    «поле: должно быть числом» (FR-41).

    Args:
        var: переменная Tkinter числового поля.
        default: значение для пустой строки.

    Returns:
        Число при удачном разборе или исходную строку.

    Raises:
        Не бросает исключений.
    """
    text = var.get().strip()
    if not text:
        return default
    try:
        return float(text) if "." in text else int(text)
    except ValueError:
        return text


def _read_optional_number(var: tk.StringVar) -> float | str | None:
    """Разобрать необязательное число: пустое поле — ``None`` (FR-12).

    Отличается от `_read_number` тем, что «не задано» и «ноль» — разные
    значения для `duration` и `background` (FR-12): пустая строка даёт
    ``None``, а «0» доходит до `validate()` и отвечает своей ошибкой.

    Args:
        var: переменная Tkinter числового поля.

    Returns:
        Число, исходная строка или ``None`` на пустом поле.

    Raises:
        Не бросает исключений.
    """
    text = var.get().strip()
    if not text:
        return None
    return _read_number(var, 0)


# since: v0.1 (FR-51, FR-55)
class VideoTimerApp:
    """Приложение: одно окно со всеми полями параметров и кнопкой рендера.

    Спека: FR-41, FR-51, FR-55, NFR-05, NFR-08. Версия: v0.1 (поле, рендер
    в потоке, прогресс, проверка ffmpeg), v0.2 (оценка, отмена, раскладка
    по макету, тема, «Открыть папку»).

    Экземпляр живёт вместе с окном: он держит ссылки на панели, поток
    рендера и найденный ffmpeg. Tkinter не терпит обращений к виджетам из
    чужого потока, поэтому поток только публикует события, а все виджеты
    трогает главный поток.

    Args:
        root: корневое окно Tkinter; передаётся извне, чтобы `main()`
            решает, создавать ли его сам.
    """

    def __init__(self, root: tk.Tk) -> None:
        """Собрать окно, панели и проверить наличие ffmpeg.

        Спека: FR-51, FR-55. Версия: v0.1.

        Порядок: панели, привязка кнопки «Рендерить», проверка ffmpeg через
        `osutil.find_ffmpeg()`. Тема `ttkbootstrap` подключается в v0.2 (FR-53;
        в v0.1 — только `ttk`). Если ffmpeg не найден, окно всё равно
        открывается, а кнопка «Рендерить» при нажатии объясняет причину
        и ничего не запускает (критерий A11).

        Args:
            root: корневое окно Tkinter.

        Returns:
            Ничего.

        Raises:
            VideoTimerError: не бросает: отсутствие ffmpeg показывается в
                интерфейсе, а не падением при запуске (FR-55).
        """
        self.root = root
        root.title(f"FastVT {__version__} — видео-таймер")
        root.minsize(540, 420)

        self.params = ParamsPanel(root)
        self.params.pack(fill="both", expand=True, side="top")
        self.render_panel = RenderPanel(root)
        self.render_panel.pack(fill="x", side="bottom")
        self.render_panel.render_button.configure(command=self.on_render)

        self.worker = RenderWorker()
        self._ffmpeg = osutil.find_ffmpeg()
        self._polling = False
        if self._ffmpeg is None:
            self.render_panel.status_label.configure(
                text=(
                    "ffmpeg не найден: установите ffmpeg "
                    "(https://ffmpeg.org) и перезапустите программу."
                )
            )

    # since: v0.1 (FR-40, FR-41)
    def build_config(self) -> TimerConfig:
        """Собрать `TimerConfig` из значений полей окна.

        Спека: FR-05, FR-06, FR-10, FR-11, FR-12, FR-40. Версия: v0.1.

        Пустые необязательные поля остаются `None`, а не превращаются в нули:
        «не задано» и «ноль» — разные значения для `duration` и
        `background` (FR-12). Проверку не выполняет — её делает `render()`
        (FR-40).

        Returns:
            Конфигурацию из текущих значений полей.

        Raises:
            VideoTimerError: не бросает; нечитаемые значения остаются
            строками и будут отсеяны `TimerConfig.validate()` с понятным
            сообщением (FR-41).
        """
        params = self.params._vars
        return TimerConfig(
            output=Path(_read_str(params["output"], ".")),
            background=_read_path(params["background"]),
            bg_color=_read_str(params["bg_color"], "black"),
            mode=_read_str(params["mode"], "stopwatch"),
            countdown_seconds=_read_number(params["countdown-seconds"], 60.0),
            duration=_read_optional_number(params["duration"]),
            position=_read_str(params["position"], "br"),
            font_size=_read_number(params["font-size"], 64),
            color=_read_str(params["color"], "white"),
            hold_seconds=_read_number(params["hold-seconds"], 5.0),
            hold_color=_read_str(params["hold-color"], "#e6362c"),
            fps=_read_number(params["fps"], 30),
        )

    # since: v0.2 (FR-30, FR-31)
    def on_estimate(self) -> None:
        """Показать приблизительную оценку длительности, размера и времени.

        Спека: FR-30, FR-31. Версия: v0.2.

        Отдельная кнопка «Рассчитать» рядом с «Рендерить». Расчёт мгновенный,
        кодирование не запускается (критерий A8). Ошибка валидации
        подсвечивает поле и выводится в статусную строку, а не в модальное
        окно.

        Returns:
            Ничего.

        Raises:
            VideoTimerError: не бросает наружу — ошибка показывается в
                статусной строке и подсветкой поля (FR-41, FR-42).
        """
        raise NotImplementedError

    # since: v0.1 (FR-51, NFR-05)
    def on_render(self) -> None:
        """Запустить рендер в фоновом потоке.

        Спека: FR-40, FR-51, FR-55, NFR-05. Версия: v0.1.

        Порядок: если ffmpeg не найден — показать инструкцию и выйти, не
        запуская рендер (критерий A11); иначе собрать `TimerConfig`, отдать
        его `RenderWorker` и включить опрос событий через `after()`.

        Returns:
            Ничего.

        Raises:
            VideoTimerError: не бросает наружу — ошибки приходят событием
                `error` из потока и показываются в статусной строке (FR-42).
        """
        if self._ffmpeg is None:
            self.render_panel.status_label.configure(
                text=(
                    "ffmpeg не найден: установите ffmpeg "
                    "(https://ffmpeg.org) и перезапустите программу."
                )
            )
            return
        try:
            cfg = self.build_config()
        except VideoTimerError as error:  # pragma: no cover - build_config не бросает
            self._show_error(error)
            return
        self.worker.start(cfg)
        self.render_panel.render_button.state(["disabled"])
        self.render_panel.progress_bar.configure(value=0)
        self._polling = True
        self._poll_loop()

    # since: v0.1 (FR-51, NFR-05)
    def _poll_events(self) -> None:
        """Забрать события из очереди потока и применить к виджетам.

        Спека: FR-51, NFR-05. Версия: v0.1.

        Единственное место, где виджеты трогаются по команде из чужого
        потока: сам поток их не касается, только кладёт события в очередь
        (NFR-05). Вызывается из `_poll_loop` по таймеру `after()`.

        Returns:
            Ничего.
        """
        for event in self.worker.poll():
            if event.kind == "progress":
                fraction, _total = event.payload
                if fraction is not None:
                    self.render_panel.progress_bar.configure(value=fraction * 100)
            elif event.kind == "done":
                result = event.payload
                self.render_panel.status_label.configure(
                    text=f"Готово: {result.output}"
                )
                self._finish_render()
            elif event.kind == "error":
                self._show_error(event.payload)

    # since: v0.1 (FR-51, NFR-05)
    def _poll_loop(self) -> None:
        """Опрашивать очередь раз в ~100 мс, пока рендер идёт.

        Спека: FR-51, NFR-05. Версия: v0.1.

        Returns:
            Ничего.
        """
        if not self._polling:
            return
        self._poll_events()
        if self.worker._running:
            self.root.after(100, self._poll_loop)
        else:
            self._polling = False

    # since: v0.1 (FR-51, FR-42)
    def _finish_render(self) -> None:
        """Вернуть окно в состояние «можно рендерить снова».

        Спека: FR-51. Версия: v0.1.

        Returns:
            Ничего.
        """
        self.render_panel.render_button.state(["!disabled"])
        self._polling = False

    # since: v0.1 (FR-41, FR-42)
    def _show_error(self, error: VideoTimerError) -> None:
        """Показать ошибку: статусная строка + подсветка поля.

        Спека: FR-41, FR-42. Версия: v0.1.

        Args:
            error: `VideoTimerError` с текстом «поле: что не так».

        Returns:
            Ничего.
        """
        self.render_panel.status_label.configure(text=str(error))
        _highlight_field(error, self.params)
        self._finish_render()

    # since: v0.2 (FR-51)
    def on_cancel(self) -> None:
        """Остановить идущий рендер.

        Спека: FR-51. Версия: v0.2 (критерий A9).

        Кнопка «Отмена» появляется в v0.2. Метод вызывает
        `RenderWorker.cancel()` и оставляет прогресс-бар как есть: итоговое
        состояние придёт событием `cancelled`, когда процесс действительно
        остановится.

        Returns:
            Ничего.

        Raises:
            Не бросает исключений.
        """
        raise NotImplementedError


# since: v0.1 (FR-51, FR-60)
def main() -> int:
    """Создать окно и запустить цикл Tkinter.

    Спека: FR-51, FR-55, FR-60, FR-61. Версия: v0.1.

    Используется и в `Запустить.bat`, и в `.app`, и в `.desktop`, поэтому
    вызов без аргументов: все пути и настройки — внутри пакета (FR-62).

    Returns:
        Код возврата процесса: 0 при штатном закрытии окна, 1 — если не
        удалось открыть дисплей.

    Raises:
        Не бросает исключений: отсутствие дисплея превращается в код 1 и
        подсказку про `GDK_BACKEND=x11` для WSLg (NFR-06) на `stderr`.
    """
    try:
        root = tk.Tk()
    except tk.TclError as error:
        print(
            f"Не удалось открыть окно Tkinter: {error}\n"
            "Нет доступа к дисплею. Для WSLg задайте GDK_BACKEND=x11 "
            "перед запуском.",
            file=sys.stderr,
        )
        return 1
    VideoTimerApp(root)
    root.mainloop()
    return 0


# since: v0.1 (FR-41)
def _highlight_field(error: VideoTimerError, panel: ParamsPanel) -> None:
    """Подсветить поле, названное в сообщении об ошибке.

    Спека: FR-41. Версия: v0.1.

    Берёт префикс сообщения до двоеточия, ищет его в `FIELD_TO_WIDGET` и
    меняет фон виджета на цвет ошибки (`FIELD_ERROR_BG`). Неизвестное поле
    не считается ошибкой: подсветка просто не происходит, текст ошибки
    остаётся в статусной строке.

    Args:
        error: исключение `VideoTimerError` с текстом «поле: что не так».
        panel: панель параметров, среди виджетов которой ищется поле.

    Returns:
        Ничего.

    Raises:
        Не бросает исключений.
    """
    field = str(error).split(":", 1)[0].strip()
    widget_name = FIELD_TO_WIDGET.get(field)
    if widget_name is None:
        return
    widget = getattr(panel, widget_name, None)
    if widget is None:
        return
    try:
        widget.configure(background=FIELD_ERROR_BG)
    except tk.TclError:
        # ttk.Combobox не даёт менять фон: пропускаем, текст ошибки виден
        # в статусной строке (FR-41).
        pass


if __name__ == "__main__":  # pragma: no cover - точка входа GUI (FR-60)
    raise SystemExit(main())
