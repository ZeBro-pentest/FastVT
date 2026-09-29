"""Запуск ffmpeg: сборка команды, прогресс, отмена, понятные ошибки.

Модуль — верхний уровень движка: `cli` и `gui` вызывают `render()`, тот
создаёт `FFmpegRenderer`. Зависимости: `config`, `background`, `filters`,
`encoders`, `osutil`. Покадровой обработки в Python нет (NFR-02) — вся
работа с видео внутри ffmpeg.

Два правила, важные для интерфейса:
    - лог ffmpeg читается потоком, в памяти держится не более 50 последних
      строк (NFR-04), наружу отдаётся только этот хвост
    - пользователю возвращается `VideoTimerError` с коротким текстом, а не
      трейсбек и не сырой лог (FR-42)
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from video_timer.config import TimerConfig, VideoTimerError

# since: v0.1 (NFR-04)
LOG_TAIL_LINES: int = 50
"""Сколько последних строк лога ffmpeg хранятся в памяти (NFR-04)."""


@dataclass
class RenderResult:
    """Результат успешного рендера.

    Спека: FR-42, FR-51. Версия: v0.1.

    Attributes:
        output: путь записанного файла.
        duration_seconds: длительность результата, если её удалось узнать
            из вывода ffmpeg; ``None`` — если не удалось, это не ошибка.
        tail_log: не более 50 последних строк лога ffmpeg для диагностики
            (NFR-04); показывается в GUI пользователю не целиком.
    """

    output: Path
    duration_seconds: float | None
    tail_log: str


# since: v0.2 (FR-51)
class RenderCancelled(VideoTimerError):
    """Рендер остановлен по требованию пользователя.

    Спека: FR-51. Версия: v0.2.

    Отдельный класс, чтобы GUI отличил отмену от ошибки: не показывает
    красное сообщение, а просто возвращает панель в исходное состояние.
    """


# since: v0.1 (FR-20, FR-51, FR-42)
class FFmpegRenderer:
    """Сборка и запуск одной команды ffmpeg.

    Спека: FR-11, FR-12, FR-13, FR-14, FR-15, FR-20, FR-23, FR-51. Версия: v0.1
    (запуск и прогресс), v0.2 (отмена, звук, качество).

    Экземпляр привязан к одной конфигурации и к одному запуску. `run()`
    можно вызвать один раз; повторный вызов на том же экземпляре не
    предусмотрен. Отмена из другого потока безопасна: `cancel()` только
    ставит флаг и завершает процесс, не трогая состояние GUI.

    Args:
        cfg: конфигурация рендера, уже проверенная `TimerConfig.validate()`.
    """

    def __init__(self, cfg: TimerConfig) -> None:
        """Запомнить конфигурацию и найти исполняемый файл ffmpeg.

        Спека: FR-55. Версия: v0.1.

        Args:
            cfg: конфигурация рендера.

        Raises:
            VideoTimerError: `ffmpeg: не найден в системе` — если ffmpeg нет
                ни в папке portable-сборки, ни в `PATH`; текст содержит
                инструкцию по установке (FR-55).
        """
        raise NotImplementedError

    # since: v0.1 (FR-13, FR-20, FR-23)
    def build_command(self) -> list[str]:
        """Собрать полный список аргументов ffmpeg для этой конфигурации.

        Спека: FR-11…FR-15, FR-20, FR-23. Версия: v0.1.

        Собирается список строк, `shell=True` не используется: пути с
        пробелами и кавычками остаются целыми аргументами. Структура:
            1. ``-y`` — перезаписать выходной файл без вопроса
            2. входные аргументы из `Background.input_args()`
            3. ``-filter_complex`` из `FilterBuilder.build()`
            4. кодек видео из `TimerConfig.resolved_encoder()`, CRF и preset
               для libx264 (FR-20, FR-23)
            5. аудиокодек, только если фон звуковой (FR-15, v0.2)
            6. ``-r`` с `cfg.fps`, путь выхода

        В v0.1 аудиокодек не добавляется: звук в версию не входит.

        Returns:
            Список аргументов, готовый для `subprocess.Popen`.

        Raises:
            VideoTimerError: если фон недоступен или не собирается цепочка
            фильтров, например не найден шрифт (FR-06).

        Пример:
            cmd = FFmpegRenderer(cfg).build_command()
            # ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=...", ...]
        """
        raise NotImplementedError

    # since: v0.1 (FR-51, NFR-04, NFR-05)
    def run(
        self, on_progress: Callable[[float, float | None], None] | None = None
    ) -> RenderResult:
        """Запустить ffmpeg и дождаться завершения, отдавая прогресс.

        Спека: FR-51, NFR-02, NFR-04, NFR-42. Версия: v0.1 (прогресс),
        v0.2 (отмена).

        Поток ffmpeg читается построчно, а не через `communicate()`: иначе
        длинный лог съедает память, а прогрессбар не двигается. Хранится
        не более :data:`LOG_TAIL_LINES` последних строк.

        Поток с `-progress pipe:2` разбирается построчно, из строк `out_time_ms`
        и `total_size` считается доля прогресса. Если общая длительность
        неизвестна, второй аргумент колбэка равен ``None`` — GUI покажет
        неопределённый индикатор.

        Args:
            on_progress: колбэк ``(доля_0..1, всего_секунд)``, вызывается в
                цикле чтения лога; ``None`` — прогресс не нужен. Вызывается
                из этого потока, поэтому GUI обязан передать безопасную
                обёртку (NFR-05).

        Returns:
            :class:`RenderResult` с путём, длительностью и хвостом лога.

        Raises:
            RenderCancelled: если до или во время работы вызвана `cancel()`
                (FR-51, v0.2).
            VideoTimerError: `render: ffmpeg завершился с ошибкой` — код
                возврата ненулевой; в конце текста — хвост лога для
                диагностики, но не весь (FR-42, NFR-04).

        Пример:
            FFmpegRenderer(cfg).run(lambda done, total: print(f"{done:.0%}"))
        """
        raise NotImplementedError

    # since: v0.2 (FR-51)
    def cancel(self) -> None:
        """Остановить идущий рендер.

        Спека: FR-51. Версия: v0.2 (критерий A9: отмена останавливает ffmpeg).

        Вызывается из потока GUI, поэтому делает только две вещи: ставит флаг
        отмены и завершает процесс ffmpeg. Метод безопасен, если рендер ещё
        не начался, и не бросает исключений, если процесс уже закончился.

        Поведение недописанного выходного файла (удалять или оставить)
        перенесено в v0.3 — открытый вопрос 4 в `SPEC.md`.
        """
        raise NotImplementedError


# since: v0.1 (FR-40, FR-50, FR-51)
def render(
    cfg: TimerConfig, on_progress: Callable[[float, float | None], None] | None = None
) -> RenderResult:
    """Проверить конфигурацию и выполнить рендер.

    Спека: FR-40, FR-42, FR-50. Версия: v0.1.

    Единственная точка входа для `cli` и `gui`: проверка и запуск всегда
    идут вместе, поэтому вызвать ffmpeg с непроверенной конфигурацией
    из интерфейса невозможно (FR-40).

    Args:
        cfg: конфигурация рендера из CLI или GUI.
        on_progress: колбэк прогресса, передаётся в `FFmpegRenderer.run()`.

    Returns:
        :class:`RenderResult` на успехе.

    Raises:
        VideoTimerError: из `TimerConfig.validate()` — с текстом «поле: что не
            так», ffmpeg при этом не запускался (критерий A7); либо из
            `FFmpegRenderer.run()` при ошибке ffmpeg (FR-42).
        RenderCancelled: при отмене рендера (v0.2).

    Пример:
        result = render(cfg)
        print(result.output)
    """
    raise NotImplementedError


# since: v0.1 (NFR-04)
def _new_log_tail() -> deque[str]:
    """Создать очередь для хранения хвоста лога ffmpeg.

    Спека: NFR-04. Версия: v0.1.

    Returns:
        Пустую `deque` с максимальной длиной :data:`LOG_TAIL_LINES`.
    """
    raise NotImplementedError
