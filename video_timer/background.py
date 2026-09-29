"""Фон рендера: видеофайл, картинка или сплошной цвет.

Модуль отвечает за то, что подаётся на вход ffmpeg: входные аргументы,
длительность и наличие звука. Всю работу с файлами делает ffmpeg и ffprobe,
покадровой обработки в Python нет (NFR-02). Зависимости: `config`;
`filters` и `renderer` импортируют этот модуль, обратных импортов нет.
"""

from __future__ import annotations

from typing import Literal

from video_timer.config import TimerConfig


# since: v0.1 (FR-10, FR-11), значение "image" — v0.2
class Background:
    """Фон, поверх которого рисуется таймер.

    Спека: FR-10, FR-11, FR-12, FR-14, FR-15. Версия: v0.1 (видео и цвет),
    v0.2 (картинка).

    Тип фона определяется один раз в конструкторе по `cfg.background` и
    расширению файла, дальше объект неизменяем. Экземпляр переиспользуется
    и `Background`, и `FilterBuilder`, и оценкой, поэтому хранит
    результат `ffprobe` и не зондирует файл повторно.

    Args:
        cfg: конфигурация рендера; должна быть уже проверена
            `TimerConfig.validate()`.
    """

    def __init__(self, cfg: TimerConfig) -> None:
        """Определить тип фона и подготовить его к использованию.

        Спека: FR-10. Версия: v0.1.

        Args:
            cfg: конфигурация рендера.

        Raises:
            VideoTimerError: `background: файл не найден` или
                `background: тип файла не поддерживается` — если путь есть,
                но расширение не входит в `VIDEO_EXTS` или `IMAGE_EXTS`.
                В v0.1 картинки ещё не принимаются.
        """
        raise NotImplementedError

    @property
    # since: v0.1 (FR-10)
    def kind(self) -> Literal["video", "image", "color"]:
        """Вернуть тип фона: видео, картинка или сплошной цвет.

        Спека: FR-10. Версия: v0.1 (`video`, `color`), v0.2 (`image`).

        Returns:
            Одно из трёх значений; ``image`` появляется в v0.2.
        """
        raise NotImplementedError

    # since: v0.1 (FR-11)
    def probe_duration(self) -> float | None:
        """Узнать длительность видео-фона через ffprobe.

        Спека: FR-11. Версия: v0.1.

        Вызывается один раз, результат запоминается. Для цвета и картинки
        возвращается `cfg.duration` без запуска ffprobe. Если ffprobe не
        найден или не отвечает, возвращается ``None`` — рендер не падает,
        длительность уточняется по факту.

        Returns:
            Длительность фона в секундах или ``None``, если её узнать нельзя.

        Raises:
            VideoTimerError: `background: не удалось прочитать файл` — только
                если файл существует, но ffprobe ответил ошибкой разбора.
        """
        raise NotImplementedError

    # since: v0.2 (FR-15)
    def has_audio(self) -> bool:
        """Проверить, есть ли у видео-фона аудиодорожка.

        Спека: FR-15. Версия: v0.2.

        Нужна, чтобы не добавлять `-map` для звука, которого нет: иначе
        ffmpeg падает на пустом потоке. Для цвета и картинки всегда ``False``.

        Returns:
            ``True``, если в файле-фоне есть хотя бы один аудиопоток.
        """
        raise NotImplementedError

    # since: v0.1 (FR-10, FR-11, FR-12)
    def input_args(self) -> list[str]:
        """Собрать входные аргументы ffmpeg для этого фона.

        Спека: FR-10, FR-11, FR-12. Версия: v0.1.

        Формы аргументов:
            - видео: ``["-i", "<путь>"]``, при `cfg.duration` добавляется
              ``-t <секунды>``, чтобы обрезать источник (FR-11)
            - картинка (v0.2): ``["-loop", "1", "-i", "<путь>"]``
            - цвет: ``["-f", "lavfi", "-i", "color=c=black:s=1280x720:r=30:d=15"]``
              — единственный способ задать конечную длительность без файла

        Пути возвращаются как есть, строкой, с платформами, понятными ffmpeg.

        Returns:
            Список аргументов, который вставляется в команду после `ffmpeg -y`
            и до `-filter_complex`.

        Пример:
            TimerConfig(output=Path("a.mp4"), bg_color="black").background
            # для сплошного цвета: ["-f", "lavfi", "-i", "color=..."]
        """
        raise NotImplementedError
