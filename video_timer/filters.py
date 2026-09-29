"""Сборка цепочки фильтров ffmpeg: масштаб фона и наложение таймера.

Модуль строит обе части `-filter_complex`: приведение фона к нужному
разрешению и `drawtext` с таймером. Зависимости: `config`, `background`,
`timeformat`; `renderer` импортирует этот модуль, обратных импортов нет.

Инвариант модуля: двоеточие и запятая внутри значения `text=` экранируются
(`\\:`, `\\,`) — иначе ffmpeg разбирает выражение как список аргументов
фильтра. Экранирование выполняет `timeformat._escape()`, повторно строка
не обрабатывается.
"""

from __future__ import annotations

from video_timer.background import Background
from video_timer.config import TimerConfig


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
        raise NotImplementedError

    # since: v0.2 (FR-13, FR-14)
    def build_scale_filter(self) -> str | None:
        """Собрать фильтр приведения фона к `resolution` и `fit`.

        Спека: FR-13, FR-14. Версия: v0.2.

        Три режима:
            - ``stretch``: ``scale=Ш:В:flags=bicubic``
            - ``contain``: ``scale`` с сохранением пропорций плюс ``pad``
              чёрными полями (критерий A3)
            - ``cover``: ``scale`` с увеличением и ``crop`` по центру
              (критерий A4)

        В v0.1 `resolution` всегда ``None``, поэтому метод возвращает
        ``None`` и цепочка ограничивается таймером.

        Returns:
            Строку фильтра или ``None``, если масштабировать нечего.

        Пример:
            build_scale_filter()  # resolution="1080x1080", fit="contain"
            # "scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2:black"
        """
        raise NotImplementedError

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
        raise NotImplementedError

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
        raise NotImplementedError
