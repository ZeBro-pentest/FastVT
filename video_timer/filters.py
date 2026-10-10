"""Сборка цепочки фильтров ffmpeg: масштаб фона и наложение таймера.

Модуль строит обе части `-filter_complex`: приведение фона к нужному
разрешению и `drawtext` с таймером. Зависимости: `config`, `background`,
`timeformat`; `renderer` импортирует этот модуль, обратных импортов нет.

Инвариант модуля: значение `text=` экранируется функцией `timeformat._escape()`
(двоеточие — двумя слэшами, запятая — одним), значение `enable=` — функцией
`timeformat._escape_enable()`. Повторно строки не обрабатываются: экранируется
только исходный текст, иначе ffmpeg нарисует лишние символы.
"""

from __future__ import annotations

from video_timer import osutil, timeformat
from video_timer.background import Background
from video_timer.config import TimerConfig, VideoTimerError
from video_timer.timeformat import (
    _escape,
    _escape_enable,
    static_clock_text,
)

# since: v0.1 (FR-01, FR-02, FR-03)
def _number(value: float) -> str:
    """Записать секунды для выражения ffmpeg без лишнего нуля.

    Спека: FR-01, FR-02, FR-03. Версия: v0.1.

    ffmpeg понимает и `10`, и `10.0`, но в выражении `between(t,10,15)`
    аккуратнее целые числа: текст в логе и тесты читаются однозначно.

    Args:
        value: количество секунд.

    Returns:
        Строку с числом: целые значения без дробной части.

    Пример:
        _number(10.0)
        # "10"
    """
    return str(int(value)) if float(value).is_integer() else str(value)


# since: v0.1 (FR-05)
_POSITION_COORDINATES: dict[str, tuple[str, str]] = {
    "tl": ("40", "40"),
    "tr": ("w-tw-40", "40"),
    "bl": ("40", "h-th-40"),
    "br": ("w-tw-40", "h-th-40"),
    "center": ("(w-tw)/2", "(h-th)/2"),
}
"""Координаты таймера для пяти позиций из `POSITIONS`.

Выражения в кавычках ffmpeg опираются на `w`, `h` — размер кадра и `tw`,
`th` — размер текста, поэтому одинаково работают для любого разрешения.
Отступ 40 пикселей выбран так, чтобы текст не лип к краю кадра (FR-05).
"""


# since: v0.1 (FR-01…FR-07, FR-13, FR-14)
class FilterBuilder:
    """Сборщик цепочки фильтров для одного рендера.

    Спека: FR-01…FR-07, FR-13, FR-14. Версия: v0.1 (таймер и подложка),
    v0.2 (масштабирование и `fit`).

    Экземпляр не запускает ffmpeg и не меняет переданные объекты: все методы
    возвращают строки, которые `FFmpegRenderer.build_command()` соединяет в
    `-filter_complex`. Порядок вызова не важен, части не дублируются.

    Args:
        cfg: конфигурация рендера, уже проверенная `TimerConfig.validate()`.
        background: фон рендера; из него берётся тип и, для картинки,
            исходное разрешение.
    """

    def __init__(self, cfg: TimerConfig, background: Background) -> None:
        """Запомнить конфигурацию и фон для последующей сборки фильтров.

        Спека: FR-13, FR-14. Версия: v0.1.

        Args:
            cfg: конфигурация рендера.
            background: фон рендера.

        Raises:
            VideoTimerError: значения не проверяются — проверка уже была
                в `TimerConfig.validate()`.
        """
        self.cfg = cfg
        self.background = background

    # since: v0.1 (FR-05, FR-06)
    def _resolve_font(self) -> str:
        """Найти файл шрифта для `drawtext`.

        Спека: FR-06. Версия: v0.1.

        Args:
            Нет.

        Returns:
            Путь к шрифту, уже пригодный для `fontfile=`.

        Raises:
            VideoTimerError: `font: не удалось найти шрифт по умолчанию` —
                если `cfg.font` не задан и системный шрифт не найден.
        """
        font = self.cfg.font
        if font is None:
            font = osutil.default_font()
        if font is None:
            raise VideoTimerError("font: не удалось найти шрифт по умолчанию")
        return str(font)

    # since: v0.1 (FR-01, FR-02, FR-03)
    def _value_expression(self) -> str:
        """Собрать выражение ffmpeg для текущего значения таймера.

        Спека: FR-01, FR-02. Версия: v0.1.

        Returns:
            `t` для секундомера и ``f"{countdown_seconds}-t"`` для отсчёта.
            Строка возвращается «сырой»: экранирование делает
            :func:`timeformat.clock_expression`.

        Пример:
            _value_expression()  # mode="countdown", countdown_seconds=10
            # "10-t"
        """
        if self.cfg.mode == "countdown":
            return f"{_number(float(self.cfg.countdown_seconds))}-t"
        return "t"

    # since: v0.1 (FR-01, FR-02, FR-03)
    def _main_enable(self) -> str | None:
        """Собрать условие показа основного таймера.

        Спека: FR-01, FR-02, FR-03. Версия: v0.1.

        Returns:
            Выражение `enable=` для `drawtext` или ``None``, когда таймер
            виден всё время. У отсчёта основной таймер гаснет в момент
            обнуления, иначе `00:00` показывался бы обычным цветом поверх
            hold-цвета (FR-03).
        """
        if self.cfg.mode != "countdown":
            return None
        return f"lt(t,{_number(float(self.cfg.countdown_seconds))})"

    # since: v0.1 (FR-03)
    def _hold_window(self) -> tuple[float, float] | None:
        """Вычислить окно показа hold-текста.

        Спека: FR-03. Версия: v0.1.

        У секундомера обнуления не бывает, поэтому окна нет. У отсчёта окно
        идёт от N до N + hold_seconds — по критерию A1 при N=10 и hold=5 это
        10…15 секунд.

        Returns:
            Пару границ окна в секундах, готовую к подстановке в выражение
            `between(t,…)`, или ``None``, если фаза выключена.
        """
        if self.cfg.mode != "countdown":
            return None
        if not self.cfg.hold_seconds:
            return None
        start = float(self.cfg.countdown_seconds)
        end = start + float(self.cfg.hold_seconds)
        return (_number(start), _number(end))

    # since: v0.1 (FR-05, FR-06)
    def _drawtext(
        self,
        text: str,
        font: str,
        coordinates: tuple[str, str],
        color: str,
        enable: str | None,
    ) -> str:
        """Собрать одну строку фильтра `drawtext`.

        Спека: FR-05, FR-06, FR-03. Версия: v0.1.

        Args:
            text: уже экранированное значение для `text=`.
            font: путь к файлу шрифта.
            coordinates: выражения для `x` и `y` из позиции (FR-05).
            color: цвет текста.
            enable: условие показа или ``None``, чтобы показывать всегда.

        Returns:
            Строку вида ``drawtext=…``, готовую для `-filter_complex`.

        Raises:
            Не бросает исключений.
        """
        x, y = coordinates
        arguments = [
            f"text={text}",
            f"fontfile={font}",
            f"fontsize={int(self.cfg.font_size)}",
            f"fontcolor={color}",
            f"x={x}",
            f"y={y}",
        ]
        if enable is not None:
            arguments.append(f"enable={_escape_enable(enable)}")
        return "drawtext=" + ":".join(arguments)

    # since: v0.2 (FR-13, FR-14)
    def build_scale_filter(self) -> str | None:
        """Собрать фильтр приведения фона к `resolution` и `fit`.

        Спека: FR-13, FR-14. Версия: v0.2 (критерии A3, A4).

        Три режима:
            - ``stretch``: ``scale=Ш:В:flags=bicubic`` — пропорции не берегутся
            - ``contain``: ``scale`` с ``force_original_aspect_ratio=decrease``
              плюс ``pad`` чёрными полями (критерий A3)
            - ``cover``: ``scale`` с ``force_original_aspect_ratio=increase``
              и ``crop`` по центру, без полей (критерий A4)

        Если `cfg.resolution` не задан, приводить фон не к чему: возвращается
        ``None``, и цепочка ограничивается таймером (FR-13).

        Returns:
            Строку фильтра или ``None``, если масштабировать нечего.

        Пример:
            build_scale_filter()  # resolution="1080x1080", fit="contain"
            # "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2:black"
        """
        resolution = self.cfg.resolution
        if resolution is None:
            return None

        width_text, height_text = resolution.split("x", 1)
        width, height = int(width_text), int(height_text)

        if self.cfg.fit == "stretch":
            return f"scale={width}:{height}:flags=bicubic"

        if self.cfg.fit == "cover":
            return (
                f"scale={width}:{height}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}"
            )

        return (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black"
        )

    # since: v0.1 (FR-01…FR-07)
    def build_timer_filters(self) -> list[str]:
        """Собрать фильтры, которые рисуют таймер и его подложку.

        Спека: FR-01, FR-02, FR-03, FR-05, FR-06, FR-07. Версия: v0.1.

        Логика:
            - значение секунд: `t` для секундомера (FR-01) и
              `countdown_seconds-t` для отсчёта (FR-02)
            - текст: выражение `timeformat.clock_expression()`, уже экранированное
            - фаза hold (FR-03): после обнуления отдельный `drawtext` с
              `hold_color`, включается выражением по времени и живёт
              `hold_seconds`; при `hold_seconds == 0` не добавляется
            - подложка `bg_style` (FR-07): тень или плашка; в v0.1 тень
            - координаты из `cfg.position` (FR-05), отступы одинаковые
            - шрифт: `cfg.font` либо `osutil.default_font()`; при отсутствии
              обоих — сообщение пользователю, а не молчаливый `None`

        Список фильтров возвращается по порядку применения, каждый элемент —
        отдельная строка, чтобы цепочку можно было разбирать по строкам.

        Returns:
            Список строк-фильтров, готовых для `-filter_complex`.

        Raises:
            VideoTimerError: `font: не удалось найти шрифт по умолчанию` —
                если не задан свой шрифт и системный тоже не найден;
                рисовать таймер нечем (FR-06).
        """
        font = self._resolve_font()
        coordinates = _POSITION_COORDINATES[self.cfg.position]
        value_expr = self._value_expression()
        clock_text = timeformat.clock_expression(value_expr, self.cfg.fmt)

        main = self._drawtext(
            clock_text, font, coordinates, self.cfg.color, self._main_enable()
        )
        filters = [main]

        if self._hold_window() is not None:
            start, end = self._hold_window()
            filters.append(
                self._drawtext(
                    _escape(static_clock_text(self.cfg.fmt)),
                    font,
                    coordinates,
                    self.cfg.hold_color,
                    f"between(t,{_number(start)},{_number(end)})",
                )
            )

        return filters

    # since: v0.1 (FR-01…FR-07, FR-13, FR-14)
    def build(self) -> list[str]:
        """Собрать полную цепочку фильтров рендера.

        Спека: FR-01…FR-07, FR-13, FR-14. Версия: v0.1.

        Вызывает `build_scale_filter()` и `build_timer_filters()`, соединяет
        результат и добавляет `format=yuv420p`, без которого mp4 с
        libx264 не собирается.

        Returns:
            Список строк-фильтров для `-filter_complex`.

        Пример:
            # сплошной чёрный фон, countdown 10 с
            ["drawtext=...", "drawtext=...", "format=yuv420p"]
        """
        chain: list[str] = []
        scale = self.build_scale_filter()
        if scale is not None:
            chain.append(scale)
        chain.extend(self.build_timer_filters())
        chain.append("format=yuv420p")
        return chain
