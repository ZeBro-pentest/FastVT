"""Панели окна и соответствие полей конфигурации виджетам.

Модуль собирает виджеты Tkinter и хранит таблицу `FIELD_TO_WIDGET`,
по которой ошибка `«поле: что не так»` превращается в подсветку нужного
поля (FR-41). Зависимости: `config` (имена полей), `timeformat` (подпись
формата часов), `panels` ничего не импортирует из движка, кроме констант.

Порядок проверок в `TimerConfig.validate()` и порядок строк в
`FIELD_TO_WIDGET` совпадают, поэтому подсвечивается первое ошибочное поле.
Новая проверка в `validate()` — одна строка в таблице.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# since: v0.1 (FR-41)
FIELD_TO_WIDGET: dict[str, str] = {
    # По одной строке на каждое проверяемое поле TimerConfig версии v0.1:
    # ключ — имя параметра в формате CLI (совпадает с префиксом сообщения
    # VideoTimerError), значение — имя атрибута виджета в ParamsPanel.
    "output": "_output_entry",
    "background": "_background_entry",
    "bg_color": "_bg_color_entry",
    "mode": "_mode_combo",
    "countdown-seconds": "_countdown_seconds_entry",
    "duration": "_duration_entry",
    "position": "_position_combo",
    "font-size": "_font_size_entry",
    "color": "_color_entry",
    "hold-seconds": "_hold_seconds_entry",
    "hold-color": "_hold_color_entry",
    "fps": "_fps_entry",
}
"""Соответствие «имя параметра → виджет» для подсветки ошибочного поля (FR-41).

Порядок строк не важен, важна полнота: на каждую проверку `validate()`
нужна одна строка, чтобы первая ошибка подсветила своё поле (FR-41).
"""


# since: v0.1 (FR-41)
FIELD_ERROR_BG = "#f8d7da"
"""Цвет фона ошибочного поля при подсветке (FR-41)."""


_FIELDS_V01: tuple[tuple[str, str, str, str, str, ...], ...] = (
    # (имя в CLI, основа атрибута, подпись, вид, значение, значения комбобокса…)
    ("output", "output", "Выходной файл", "entry", ""),
    ("background", "background", "Фон (видео/картинка)", "entry", ""),
    ("bg_color", "bg_color", "Цвет фона", "entry", "black"),
    ("mode", "mode", "Режим", "combo", "stopwatch", "stopwatch", "countdown"),
    (
        "countdown-seconds",
        "countdown_seconds",
        "Старт отсчёта, сек",
        "entry",
        "60",
    ),
    ("duration", "duration", "Длительность, сек", "entry", ""),
    (
        "position",
        "position",
        "Положение",
        "combo",
        "br",
        "tl",
        "tr",
        "bl",
        "br",
        "center",
    ),
    ("font-size", "font_size", "Размер шрифта", "entry", "64"),
    ("color", "color", "Цвет текста", "entry", "white"),
    ("hold-seconds", "hold_seconds", "Пауза на 00:00, сек", "entry", "5"),
    ("hold-color", "hold_color", "Цвет 00:00", "entry", "#e6362c"),
    ("fps", "fps", "Кадров/сек", "entry", "30"),
)
"""Поля версии v0.1: имя CLI, основа атрибута, подпись, вид и значения по умолчанию."""


# since: v0.1 (FR-51)
class ToolbarPanel(ttk.Frame):
    """Верхняя панель окна: открыть, сохранить как, пресеты, справка.

    Спека: FR-52, FR-56. Версия: v0.1 (минимальный набор кнопок),
    v0.2 (полный макет и пресеты).

    Args:
        parent: родительский виджет, к которому панель подшивается.
    """

    def __init__(self, parent: tk.Misc) -> None:
        """Создать панель и разместить в ней кнопки верхнего ряда.

        Спека: FR-52. Версия: v0.1.

        Args:
            parent: родительский виджет.

        Returns:
            Ничего.

        Raises:
            tk.TclError: если родитель уже уничтожен; стандартное поведение
            Tkinter, не перехватывается.
        """
        raise NotImplementedError


# since: v0.2 (FR-52)
class CanvasPanel(ttk.Frame):
    """Центральная область: холст с превью кадра.

    Спека: FR-32, FR-52. Версия: v0.2 (в v0.1 остаётся пустым местом).

    Args:
        parent: родительский виджет, к которому панель подшивается.
    """

    def __init__(self, parent: tk.Misc) -> None:
        """Создать панель с холстом, который сам по себе ничего не рисует.

        Спека: FR-52. Версия: v0.2.

        Args:
            parent: родительский виджет.

        Returns:
            Ничего.

        Raises:
            tk.TclError: если родитель уже уничтожен.
        """
        raise NotImplementedError


# since: v0.2 (FR-52)
class LogPanel(ttk.Frame):
    """Боковая панель журнала: последние строки лога ffmpeg.

    Спека: FR-52, NFR-04. Версия: v0.2 (в v0.1 журнала нет).

    Показывает не более 50 последних строк, как и `renderer` их хранит:
    длинный лог в виджете тормозит интерфейс.

    Args:
        parent: родительский виджет, к которому панель подшивается.
    """

    def __init__(self, parent: tk.Misc) -> None:
        """Создать свёртываемую панель с текстовым виджетом журнала.

        Спека: FR-52, NFR-04. Версия: v0.2.

        Args:
            parent: родительский виджет.

        Returns:
            Ничего.

        Raises:
            tk.TclError: если родитель уже уничтожен.
        """
        raise NotImplementedError


# since: v0.1 (FR-51)
class ParamsPanel(ttk.Frame):
    """Левая колонка параметров: поля `TimerConfig` версии v0.1.

    Спека: FR-05, FR-06, FR-10, FR-11, FR-12, FR-41, FR-51. Версия: v0.1
    (поля из `specs/v0.1.md`), v0.2 (секции по макету).

    Каждому полю соответствует переменная Tkinter (`StringVar` /
    `IntVar` / `DoubleVar`) с префиксом `_`, чтобы `VideoTimerApp.build_config()`
    читала их напрямую. Имена переменных перечислены в `FIELD_TO_WIDGET`.

    Args:
        parent: родительский виджет, к которому панель подшивается.
    """

    def __init__(self, parent: tk.Misc) -> None:
        """Создать панель и все поля параметров версии v0.1.

        Спека: FR-51, FR-41. Версия: v0.1.

        Поля версии v0.1: выходной файл, фон (цвет или видеофайл), режим,
        `countdown-seconds`, `duration`, `position`, `font-size`, `color`,
        `hold-seconds`, `hold-color`, `fps`. Формат часов зафиксирован на
        `мм:сс` и показывается подписью, полем не управляется (FR-04).

        Каждому полю соответствует `StringVar` в `self._vars` (по имени в
        формате CLI) и виджет-атрибут по имени из `FIELD_TO_WIDGET`.
        «Ошибка → подсветка» находит виджет по таблице (FR-41).

        Args:
            parent: родительский виджет.

        Returns:
            Ничего.

        Raises:
            tk.TclError: если родитель уже уничтожен.
        """
        super().__init__(parent, padding=8)
        self._vars: dict[str, tk.StringVar] = {}
        self._widgets: dict[str, tk.Widget] = {}
        for row, field in enumerate(_FIELDS_V01):
            name, base, label, kind, default, *values = field
            var = tk.StringVar(self, value=default)
            self._vars[name] = var
            setattr(self, f"_{base}_var", var)
            ttk.Label(self, text=label).grid(row=row, column=0, sticky="w", pady=2)
            if kind == "combo":
                widget = ttk.Combobox(
                    self, textvariable=var, values=values, state="readonly", width=28
                )
                suffix = "combo"
            else:
                widget = tk.Entry(
                    self, textvariable=var, width=30, background="white"
                )
                suffix = "entry"
            widget.grid(row=row, column=1, sticky="ew", pady=2, padx=(8, 0))
            self._widgets[name] = widget
            setattr(self, f"_{base}_{suffix}", widget)
        ttk.Label(self, text="Формат часов: мм:сс (фиксирован, FR-04)").grid(
            row=len(_FIELDS_V01), column=0, columnspan=2, sticky="w", pady=(8, 0)
        )
        self.columnconfigure(1, weight=1)


# since: v0.1 (FR-51)
class RenderPanel(ttk.Frame):
    """Нижняя правая панель: оценка, кнопки «Рендерить» и «Отмена», прогресс.

    Спека: FR-30, FR-31, FR-51, FR-54. Версия: v0.1 (кнопка и прогресс-бар),
    v0.2 (оценка, отмена, «Открыть папку»).

    Args:
        parent: родительский виджет, к которому панель подшивается.
    """

    def __init__(self, parent: tk.Misc) -> None:
        """Создать панель с прогресс-баром и кнопкой «Рендерить».

        Спека: FR-51. Версия: v0.1.

        В v0.1 кнопка «Отмена» отсутствует (FR-51 без отмены): она
        появляется в v0.2 вместе с `RenderWorker.cancel()`.

        Args:
            parent: родительский виджет.

        Returns:
            Ничего.

        Raises:
            tk.TclError: если родитель уже уничтожен.
        """
        super().__init__(parent, padding=8)
        self.status_label = ttk.Label(self, text="", anchor="w", wraplength=460)
        self.status_label.pack(fill="x")
        self.progress_bar = ttk.Progressbar(
            self, orient="horizontal", mode="determinate", maximum=100
        )
        self.progress_bar.pack(fill="x", pady=(6, 0))
        self.render_button = ttk.Button(self, text="Рендерить")
        self.render_button.pack(side="right", pady=(6, 0))
