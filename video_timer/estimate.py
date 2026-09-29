"""Приблизительная оценка результата рендера без запуска кодирования.

Модуль отвечает на вопрос «сколько будет длиться, весить и сколько
рендериться» до нажатия кнопки «Рендерить». Зависимости: `config`,
`background`; `renderer` и `gui` импортируют этот модуль, обратных
импортов нет.

Все числа — порядок величины (SPEC 7.5): формула строится по разрешению,
CRF и длительности, без запроса характеристик процессора и видеокарты.
Точность не обещается, поэтому `RenderEstimate.note` всегда содержит
пометку «приблизительно».
"""

from __future__ import annotations

from dataclasses import dataclass

from video_timer.background import Background
from video_timer.config import TimerConfig

# since: v0.2 (FR-23)
DEFAULT_RESOLUTION: str = "1280x720"
"""Разрешение по умолчанию, если в конфигурации своё не задано (FR-13)."""


@dataclass
class RenderEstimate:
    """Приблизительные характеристики будущего файла.

    Спека: FR-30, FR-31. Версия: v0.2.

    Значения заполняются функцией :func:`estimate` и показываются в GUI
    перед кнопкой «Рендерить». Поля — простые числа, чтобы их можно было
    показать и отформатировать на месте.

    Attributes:
        duration_seconds: ожидаемая длительность результата в секундах.
        estimated_size_mb: ожидаемый размер файла в мегабайтах.
        estimated_render_seconds: ожидаемое время кодирования в секундах.
        note: пометка о приблизительности и о том, от чего зависел расчёт.
    """

    duration_seconds: float
    estimated_size_mb: float
    estimated_render_seconds: float
    note: str


# since: v0.2 (FR-30)
def estimate(cfg: TimerConfig, background: Background) -> RenderEstimate:
    """Оценить длительность, размер и время рендера без запуска ffmpeg.

    Спека: FR-30, FR-31. Версия: v0.2 (критерий A8: ответ мгновенный,
    кодирование не запускается).

    Расчёт:
        - длительность берётся из `TimerConfig.known_total_duration()`, а если
          там ``None`` — из `Background.probe_duration()`
        - размер — по числу бит на пиксель, зависящему от разрешения и CRF
        - время — длина результата, делённая на коэффициент скорости кодека
          для данного режима (CPU-`libx264` заметно медленнее GPU-кодеков)

    Args:
        cfg: конфигурация рендера, уже проверенная `TimerConfig.validate()`.
        background: фон рендера, чтобы узнать длительность видеофона.

    Returns:
        :class:`RenderEstimate` с округлёнными значениями и пометкой
        «приблизительно».

    Raises:
        VideoTimerError: та же ошибка, что и `TimerConfig.validate()` —
            оценивать имеет смысл только проверенную конфигурацию (FR-40).

    Пример:
        estimate(cfg, background).estimated_size_mb  # например, 18.4
    """
    raise NotImplementedError
