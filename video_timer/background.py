"""Фон рендера: видеофайл, картинка или сплошной цвет.

Модуль отвечает за то, что подаётся на вход ffmpeg: входные аргументы,
длительность и наличие звука. Всю работу с файлами делает ffmpeg и ffprobe,
покадровой обработки в Python нет (NFR-02). Зависимости: `config`, `osutil`;
`filters` и `renderer` импортируют этот модуль, обратных импортов нет.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Literal

from video_timer import osutil
from video_timer.config import IMAGE_EXTS, VIDEO_EXTS, TimerConfig, VideoTimerError

_UNKNOWN: object = object()
"""Отметка «длительность ещё не зондировалась» (FFmpeg длина известна не всегда)."""


# since: v0.1 (FR-10, FR-11), v0.2 (FR-13)
DEFAULT_RESOLUTION: str = "1920x1080"
"""Разрешение сплошного цвета, если `resolution` не задан (SPEC 4.1, FR-13)."""


# since: v0.1 (FR-11, FR-12)
def _seconds(value: float) -> str:
    """Записать секунды для аргумента ffmpeg без лишнего нуля.

    Спека: FR-11, FR-12. Версия: v0.1.

    ffmpeg понимает и `15`, и `15.0`, но целое число читается в логе
    однозначно и не отличается от того, что впишет пользователь.

    Args:
        value: количество секунд.

    Returns:
        Строку с числом: целые значения без дробной части.

    Пример:
        _seconds(15.0)
        # "15"
    """
    return str(int(value)) if float(value).is_integer() else str(value)


# since: v0.1 (FR-11)
def _run_ffprobe(path: Path) -> float | None:
    """Узнать длительность видеофайла через ffprobe.

    Спека: FR-11. Версия: v0.1.

    Единственное место, где модуль запускает внешнюю программу. Отсутствие
    ffprobe — не ошибка: возвращается ``None``, длительность уточнится по
    ходу рендера. Ошибка разбора существующего файла — уже ошибка
    пользователя, из неё делается короткое сообщение без лога ffmpeg (FR-42).

    Args:
        path: путь к видеофайлу-фону.

    Returns:
        Длительность в секундах или ``None``, если ffprobe нет или он
        не смог разобрать файл.

    Raises:
        VideoTimerError: `background: не удалось прочитать файл` — если ffprobe
            найден, но ответ не содержит ожидаемого поля длительности.
    """
    probe = osutil.find_ffprobe()
    if probe is None:
        return None

    command = [
        str(probe),
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        finished = subprocess.run(
            command, capture_output=True, text=True, check=False
        )
    except OSError:
        return None

    if finished.returncode != 0:
        return None

    try:
        payload = json.loads(finished.stdout)
        return float(payload["format"]["duration"])
    except (ValueError, KeyError, TypeError):
        raise VideoTimerError("background: не удалось прочитать файл") from None


# since: v0.2 (FR-15)
def _run_ffprobe_audio(path: Path) -> bool:
    """Проверить через ffprobe, есть ли у файла аудиодорожка.

    Спека: FR-15. Версия: v0.2.

    Читаются только потоки-аудио (`-select_streams a`), чтобы тяжёлый разбор
    всех дорожек не запускался ради одного «есть звук / нет звука». Если
    ffprobe нет или файл не разобрался, возвращается ``False``: рендер
    продолжает работу без звука, а не падает (FR-42, FR-55).

    Args:
        path: путь к видео-фону.

    Returns:
        ``True``, если в файле есть хотя бы один аудиопоток.

    Raises:
        Не бросает исключений: любая проблема трактуется как «звука нет».
    """
    probe = osutil.find_ffprobe()
    if probe is None:
        return False

    command = [
        str(probe),
        "-v",
        "error",
        "-select_streams",
        "a",
        "-show_entries",
        "stream=index",
        "-of",
        "json",
        str(path),
    ]
    try:
        finished = subprocess.run(
            command, capture_output=True, text=True, check=False
        )
    except OSError:
        return False

    if finished.returncode != 0:
        return False

    try:
        payload = json.loads(finished.stdout)
    except ValueError:
        return False

    streams = payload.get("streams")
    return bool(streams)


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

        Спека: FR-10. Версия: v0.1 (видео, цвет), v0.2 (картинка).

        Args:
            cfg: конфигурация рендера.

        Raises:
            VideoTimerError: `background: файл не найден` или
                `background: тип файла не поддерживается` — если путь есть,
                но расширение не входит в `VIDEO_EXTS` или `IMAGE_EXTS`.
        """
        self.cfg = cfg
        self._kind: Literal["video", "image", "color"] = "color"
        self._duration: float | None | object = _UNKNOWN
        self._audio: bool | object = _UNKNOWN

        if cfg.background is None:
            return

        if not cfg.background.exists():
            raise VideoTimerError("background: файл не найден")

        suffix = cfg.background.suffix.lower()
        if suffix in VIDEO_EXTS:
            self._kind = "video"
        elif suffix in IMAGE_EXTS:
            self._kind = "image"
        else:
            raise VideoTimerError("background: тип файла не поддерживается")

    @property
    # since: v0.1 (FR-10)
    def kind(self) -> Literal["video", "image", "color"]:
        """Вернуть тип фона: видео, картинка или сплошной цвет.

        Спека: FR-10. Версия: v0.1 (`video`, `color`), v0.2 (`image`).

        Returns:
            Одно из трёх значений; ``image`` появляется в v0.2.
        """
        return self._kind

    # since: v0.1 (FR-11), v0.2 (FR-12)
    def probe_duration(self) -> float | None:
        """Узнать длительность видео-фона через ffprobe.

        Спека: FR-11, FR-12. Версия: v0.1 (видео), v0.2 (картинка).

        Вызывается один раз, результат запоминается. Для цвета и картинки
        длительность известна заранее и возвращается через
        `cfg.known_total_duration()` без запуска ffprobe (FR-12). Если ffprobe
        не найден или не отвечает, возвращается ``None`` — рендер не падает,
        длительность уточняется по факту.

        Returns:
            Длительность фона в секундах или ``None``, если её узнать нельзя.

        Raises:
            VideoTimerError: `background: не удалось прочитать файл` — только
                если файл существует, но ffprobe ответил ошибкой разбора.
        """
        if self._kind in ("color", "image"):
            return self.cfg.known_total_duration()

        if self._duration is not _UNKNOWN:
            return self._duration

        result = _run_ffprobe(self.cfg.background) if self.cfg.background else None
        self._duration = result
        return self._duration

    # since: v0.2 (FR-15)
    def has_audio(self) -> bool:
        """Проверить, есть ли у видео-фона аудиодорожка.

        Спека: FR-15. Версия: v0.2.

        Нужна, чтобы не добавлять `-map` для звука, которого нет: иначе
        ffmpeg падает на пустом потоке. Для цвета и картинки всегда ``False``,
        ffprobe не запускается. Результат зондирования запоминается.

        Returns:
            ``True``, если в файле-фоне есть хотя бы один аудиопоток.
        """
        if self._kind != "video" or self.cfg.background is None:
            return False

        if self._audio is not _UNKNOWN:
            return bool(self._audio)

        self._audio = _run_ffprobe_audio(self.cfg.background)
        return bool(self._audio)

    # since: v0.1 (FR-10, FR-11, FR-12), v0.2 (FR-10, FR-12)
    def input_args(self) -> list[str]:
        """Собрать входные аргументы ffmpeg для этого фона.

        Спека: FR-10, FR-11, FR-12. Версия: v0.1 (видео, цвет), v0.2 (картинка).

        Формы аргументов:
            - видео: ``["-i", "<путь>"]``, при `cfg.duration` добавляется
              ``-t <секунды>``, чтобы обрезать источник (FR-11)
            - картинка (v0.2): ``["-loop", "1", "-i", "<путь>"]`` плюс
              ``-t <секунды>`` — без ограничения зацикленный кадр бесконечен
              (FR-10, FR-12)
            - цвет: ``["-f", "lavfi", "-i", "color=c=black:s=1920x1080:r=30:d=15"]``
              — единственный способ задать конечную длительность без файла;
              размер 1920x1080 берётся, если `resolution` не задан (SPEC 4.1)

        Пути возвращаются как есть, строкой, с платформами, понятными ffmpeg.

        Returns:
            Список аргументов, который вставляется в команду после `ffmpeg -y`
            и до `-filter_complex`.

        Пример:
            TimerConfig(output=Path("a.mp4"), bg_color="black").background
            # для сплошного цвета: ["-f", "lavfi", "-i", "color=..."]
        """
        if self._kind == "video" and self.cfg.background is not None:
            args: list[str] = ["-i", str(self.cfg.background)]
            if self.cfg.duration is not None:
                args.extend(["-t", _seconds(self.cfg.duration)])
            return args

        if self._kind == "image" and self.cfg.background is not None:
            args = ["-loop", "1", "-i", str(self.cfg.background)]
            total = self.probe_duration()
            if total is not None:
                args.extend(["-t", _seconds(total)])
            return args

        duration = self.probe_duration() or 0.0
        source = (
            f"color=c={self.cfg.bg_color}:"
            f"s={self.cfg.resolution or DEFAULT_RESOLUTION}:"
            f"r={self.cfg.fps}:d={_seconds(duration)}"
        )
        return ["-f", "lavfi", "-i", source]
