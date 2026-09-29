"""Поток рендера и очередь событий для GUI.

GUI не должен блокироваться во время кодирования (NFR-05), поэтому рендер
выполняется в отдельном потоке, а главный поток раз в ~100 мс забирает
события из очереди. Модуль — единственное место, где живёт этот поток.

Зависимости: `config`, `renderer`. Tkinter сюда не импортируется: очередь
`queue.Queue` обычная, виджеты трогает только `app`.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass
from typing import Literal

from video_timer.config import TimerConfig


@dataclass
class WorkerEvent:
    """Одно событие от потока рендера.

    Спека: FR-51, NFR-05. Версия: v0.1 (``progress``, ``done``, ``error``),
    v0.2 (``cancelled``).

    События различаются видом, а не типом, чтобы главный поток обрабатывал
    их одним циклом и не зависел от конкретного формата ошибки.

    Attributes:
        kind: вид события: ``progress`` — доля выполнения, ``done`` — успех,
            ``error`` — ошибка рендера, ``cancelled`` — отмена (v0.2).
        payload: содержимое: для ``progress`` — кортеж ``(доля, всего_секунд)``,
            для ``done`` — `renderer.RenderResult`, для ``error`` —
            `VideoTimerError` с коротким текстом, для ``cancelled`` — ``None``.
    """

    kind: Literal["progress", "done", "error", "cancelled"]
    payload: object


# since: v0.1 (FR-51, NFR-05)
class RenderWorker:
    """Фоновый поток, выполняющий рендер и публикующий события.

    Спека: FR-51, NFR-05. Версия: v0.1 (запуск и прогресс), v0.2 (отмена).

    Экземпляр живёт столько же, сколько окно. Поток демонический: при
    закрытии окна он не держит интерпретатор. Очередь ограничена, чтобы
    забытый получатель не съел память при длинном рендере.

    Args:
        Нет. Конфигурация передаётся в `start()`.
    """

    def __init__(self) -> None:
        """Создать очередь событий, не запуская поток.

        Спека: FR-51, NFR-05. Версия: v0.1.

        Returns:
            Ничего.

        Raises:
            Не бросает исключений.
        """
        raise NotImplementedError

    # since: v0.1 (FR-51)
    def start(self, cfg: TimerConfig) -> None:
        """Запустить рендер в отдельном потоке.

        Спека: FR-40, FR-51, NFR-05. Версия: v0.1.

        Поток вызывает `renderer.render()` и кладёт в очередь `done` с
        результатом либо `error` с `VideoTimerError`. Проверка конфигурации
        остаётся внутри `render()`, поэтому кнопка «Рендерить» не должна
        вызывать `validate()` сам (FR-40).

        Args:
            cfg: конфигурация рендера, собранная из полей окна.

        Returns:
            Ничего.

        Raises:
            VideoTimerError: если рендер уже идёт — второй вызов игнорируется,
            чтобы не завести два процесса ffmpeg на один выходной файл.
        """
        raise NotImplementedError

    # since: v0.2 (FR-51)
    def cancel(self) -> None:
        """Попросить поток остановить рендер.

        Спека: FR-51. Версия: v0.2 (критерий A9).

        Вызывается из главного потока, поэтому только ставит флаг и передаёт
        его рендереру. Событие ``cancelled`` приходит из потока рендера,
        когда тот действительно остановился.

        Returns:
            Ничего.

        Raises:
            Не бросает исключений, даже если рендер не запускался.
        """
        raise NotImplementedError

    # since: v0.1 (FR-51, NFR-05)
    def poll(self) -> list[WorkerEvent]:
        """Забрать из очереди все накопленные события.

        Спека: FR-51, NFR-05. Версия: v0.1.

        Вызывается главным потоком по таймеру `after()`. Возвращает список,
        чтобы обработать пачку прогресса одним проходом отрисовки; пустой
        список означает «ничего нового».

        Returns:
            Список событий в порядке поступления; пустой, если очередь пуста.

        Пример:
            for event in worker.poll():
                if event.kind == "progress":
                    progress_bar["value"] = event.payload[0] * 100
        """
        raise NotImplementedError


# since: v0.1 (NFR-05)
def _make_queue() -> queue.Queue[WorkerEvent]:
    """Создать ограниченную очередь событий.

    Спека: NFR-05. Версия: v0.1.

    Размер ограничен: если главный поток перестал забирать события,
    новые прогресс-сообщения вытесняют старые, а не растут без границ.

    Returns:
        Пустую очередь для `WorkerEvent`.
    """
    raise NotImplementedError


# since: v0.1 (NFR-05)
def _thread_target(
    cfg: TimerConfig, events: queue.Queue[WorkerEvent], cancel_flag: threading.Event
) -> None:
    """Описать тело потока рендера.

    Спека: FR-51, NFR-05, FR-42. Версия: v0.1.

    Args:
        cfg: конфигурация рендера.
        events: очередь, в которую кладутся события.
        cancel_flag: флаг отмены, который проверяет рендерер.

    Returns:
        Ничего.

    Raises:
        Исключения не выпускаются наружу: `VideoTimerError` кладётся в
        очередь как событие `error`, чтобы главный поток не падал (FR-42).
    """
    raise NotImplementedError
