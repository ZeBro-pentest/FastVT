"""Конфигурация рендера, константы предметной области и проверка параметров.

Модуль — нижний уровень пакета. Зависимости: только стандартная библиотека.
Импортируется остальными модулями (`filters`, `background`, `encoders`,
`renderer`, `cli`, `gui`), сам ничего из них не импортирует.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

# since: v0.1 (FR-05)
POSITIONS: tuple[str, ...] = ("tl", "tr", "bl", "br", "center")
"""Допустимые позиции таймера: четыре угла и центр (FR-05)."""

# since: v0.2 (FR-07)
BG_STYLES: tuple[str, ...] = ("none", "shadow", "box")
"""Допустимые подложки под текст: нет, тень, плашка (FR-07)."""

# since: v0.2 (FR-14)
FIT_MODES: tuple[str, ...] = ("stretch", "contain", "cover")
"""Допустимые способы вписать фон в разрешение: растянуть, с полями, обрезать (FR-14)."""

# since: v0.1 (FR-20), полный список — v0.2
FORMATS: tuple[str, ...] = (".mp4", ".mov", ".mkv", ".webm")
"""Расширения выходных файлов (FR-20).

В v0.1 допустим только ``.mp4`` (libx264). Остальные расширения включаются
в v0.2 вместе с выбором кодека.
"""

# since: v0.1 (FR-10)
VIDEO_EXTS: tuple[str, ...] = (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")
"""Расширения файлов, которые принимаются как видео-фон (FR-10, FR-11)."""

# since: v0.2 (FR-10)
IMAGE_EXTS: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
"""Расширения файлов, которые принимаются как картинка-фон (FR-10)."""

# since: v0.1 (FR-06, FR-10)
COLOR_NAMES: tuple[str, ...] = (
    "black",
    "white",
    "red",
    "green",
    "blue",
    "yellow",
    "cyan",
    "magenta",
    "gray",
    "grey",
    "orange",
    "purple",
)
"""Белый список имён цветов для `bg_color`, `color`, `hold_color`.

Дополнительно допустимы формы ``#rgb`` и ``#rrggbb`` (SPEC 7.1).
Список цветов ffmpeg шире, но интерфейс ограничен этими именами, чтобы
ошибка в поле всегда читалась однозначно (FR-41).
"""


# since: v0.1 (FR-41, FR-42)
class VideoTimerError(RuntimeError):
    """Ошибка, которую можно показать пользователю.

    Текст сообщения имеет вид ``«поле: что не так»``: префикс до двоеточия —
    имя параметра в формате CLI (``font-size``), GUI по нему подсвечивает
    поле (FR-41). Трейсбек и сырой лог ffmpeg в сообщение не попадают (FR-42).
    """


@dataclass
class TimerConfig:
    """Полный набор параметров одного рендера.

    Спека: FR-01…FR-06, FR-10…FR-15, FR-20…FR-23. Версия: v0.1 (часть полей
    проверяется с v0.2, но объявлена сразу — интерфейс не меняется).

    Присваивается как есть, без копирования и без побочных эффектов; перед
    любым запуском ffmpeg вызывается :meth:`validate`.

    Args:
        output: путь итогового файла; расширение из :data:`FORMATS` (FR-20).
        background: путь к видео-фону или картинке; ``None`` — фон сплошного
            цвета (FR-10).
        bg_color: цвет фона: ``#rgb``, ``#rrggbb`` или имя из
            :data:`COLOR_NAMES` (FR-10).
        mode: ``stopwatch`` (значение растёт от нуля) или ``countdown``
            (значение падает от N) (FR-01, FR-02).
        countdown_seconds: стартовое значение N обратного отсчёта в секундах
            (FR-02).
        duration: длина результата в секундах; ``None`` — взять из видео-фона
            (FR-11) или вычислить для countdown (FR-12).
        fmt: формат часов: ``mmss``, ``hhmmss``, ``mmssms`` (FR-04).
        position: положение таймера из :data:`POSITIONS` (FR-05).
        font: путь к своему шрифту ``.ttf`` / ``.otf`` / ``.ttc``;
            ``None`` — системный шрифт по умолчанию (FR-06).
        font_size: размер шрифта в пикселях, 8…500 (FR-06).
        color: цвет основного текста (FR-06).
        hold_seconds: сколько секунд после обнуления горит ``00:00``
            hold-цветом; ``0`` — не показывать (FR-03).
        hold_color: цвет ``00:00`` в фазе hold (FR-03).
        bg_style: подложка под текстом из :data:`BG_STYLES` (FR-07).
        resolution: желаемое разрешение ``ШxВ``; ``None`` — как у источника
            или ``1280x720`` для сплошного цвета (FR-13).
        fit: способ вписать фон в `resolution` из :data:`FIT_MODES` (FR-14).
        fps: частота кадров результата, 1…120 (FR-13).
        encoder: явный кодек видео; ``None`` — подобрать по расширению (FR-21).
        crf: качество кодирования для libx264, 0…51 (FR-23).
        preset: пресет скорости кодирования для libx264 (FR-23).
    """

    output: Path
    background: Path | None = None
    bg_color: str = "black"
    mode: Literal["stopwatch", "countdown"] = "stopwatch"
    countdown_seconds: float = 60.0
    duration: float | None = None
    fmt: Literal["mmss", "hhmmss", "mmssms"] = "mmss"
    position: Literal["tl", "tr", "bl", "br", "center"] = "br"
    font: Path | None = None
    font_size: int = 64
    color: str = "white"
    hold_seconds: float = 5.0
    hold_color: str = "#e6362c"
    bg_style: Literal["none", "shadow", "box"] = "shadow"
    resolution: str | None = None
    fit: Literal["stretch", "contain", "cover"] = "contain"
    fps: int = 30
    encoder: str | None = None
    crf: int = 18
    preset: str = "medium"

    # since: v0.1 (FR-40, FR-41, FR-42)
    def validate(self) -> None:
        """Проверить все поля конфигурации до запуска ffmpeg.

        Спека: FR-40, FR-41, FR-42. Версия: v0.1 (поля v0.2+ пока не проверяются).

        Проверки v0.1:
            - `output`: расширение `.mp4` (FR-20, полный список — v0.2)
            - `background`: файл существует; расширение из `VIDEO_EXTS` (FR-10)
            - `bg_color`, `color`, `hold_color`: `#rgb`, `#rrggbb` или имя из
              `COLOR_NAMES` (FR-06, FR-10)
            - `mode`: одно из двух значений (FR-01, FR-02)
            - `countdown_seconds`: > 0 при `mode == "countdown"` (FR-02)
            - `duration`: > 0, если задан; обязателен для stopwatch без
              видео-фона (FR-12)
            - `position`: одно из `POSITIONS` (FR-05)
            - `font_size`: 8…500 (FR-06)
            - `hold_seconds`: >= 0 (FR-03)
            - `fps`: 1…120 (FR-13)
            - если фона-видео нет и `mode == "countdown"`, результат
              считается равным `countdown_seconds + hold_seconds` (FR-12)

        Проверки v0.2 (объявлены, выполняются позже):
            - `fmt`: одно из `mmss`, `hhmmss`, `mmssms` (FR-04)
            - `font`: файл существует, расширение `.ttf` / `.otf` / `.ttc` (FR-06)
            - `bg_style`: одно из `BG_STYLES` (FR-07)
            - `resolution`: `^\\d+x\\d+$`, обе стороны > 0 (FR-13)
            - `fit`: одно из `FIT_MODES` (FR-14)
            - `crf`: 0…51 при libx264 (FR-23)
            - `encoder`: совместим с контейнером (FR-21)

        Порядок проверок — от первого поля к последнему, чтобы в GUI
        подсвечивалось только первое ошибочное поле.

        Raises:
            VideoTimerError: сообщение вида «поле: что не так»; поле — имя
                параметра в формате CLI (например, ``font-size``). В тексте
                используется только первая ошибка.

        Пример:
            TimerConfig(output=Path("a.mp4"), font_size=0).validate()
            # VideoTimerError: font-size: должен быть от 8 до 500
        """
        raise NotImplementedError

    # since: v0.1 (FR-20), выбор по контейнеру — v0.2 (FR-21)
    def resolved_encoder(self) -> str:
        """Вернуть кодек видео, которым будет записан результат.

        Спека: FR-20, FR-21, FR-22. Версия: v0.1.

        В v0.1 выбор не требуется: вывод только `.mp4`, кодек зафиксирован
        как ``libx264``. В v0.2 при заданном `encoder` возвращается он,
        иначе кодек берётся из ``encoders.OUTPUT_CODECS`` по расширению
        `output`; импорт делается внутри метода, потому что `encoders`
        зависит от `config`, и обратный импорт на уровне модуля запрещён.

        Returns:
            Имя кодека видео, как его понимает ffmpeg, например ``libx264``.

        Raises:
            VideoTimerError: `encoder: кодек несовместим с расширением вывода`
                (FR-21) или `encoder: кодек не найден в сборке ffmpeg` (FR-22);
                обе проверки — v0.2.

        Пример:
            TimerConfig(output=Path("a.mp4")).resolved_encoder()
            # "libx264"
        """
        raise NotImplementedError

    # since: v0.1 (FR-11, FR-12)
    def known_total_duration(self) -> float | None:
        """Вернуть длительность результата, если её можно узнать без ffprobe.

        Спека: FR-11, FR-12. Версия: v0.1.

        Правила:
            - сплошной цвет или картинка, `mode == "countdown"`:
              `countdown_seconds + hold_seconds` (FR-12)
            - сплошной цвет или картинка, `mode == "stopwatch"`: `duration`
              (обязателен, иначе `validate()` уже ругалась) (FR-12)
            - видео-фон: `duration`, если задан, иначе ``None`` — точную
              длительность знает только `Background.probe_duration()` (FR-11)

        Нужен, чтобы прогресс-бар и оценка не требовали запуска ffprobe.

        Returns:
            Длительность в секундах или ``None``, если длительность определяется
            только после зондирования файла-фона.

        Пример:
            cfg = TimerConfig(output=Path("a.mp4"), mode="countdown",
                              countdown_seconds=10.0, hold_seconds=5.0)
            cfg.known_total_duration()
            # 15.0
        """
        raise NotImplementedError
