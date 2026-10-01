"""Поиск внешних программ, шрифта по умолчанию и открытие папки.

Модуль заменяет `platform.py` из `SPEC.md` 6: имя перекрывает стандартный
модуль `platform`, поэтому здесь `osutil.py`. Содержит только работу с
системой — ни знаний о таймере, ни сборки команд. Зависимости: стандартная
библиотека. Импортируется `renderer` и `gui`, сам ничего из пакета
не импортирует.

Порядок поиска ffmpeg (SPEC 7.7): сначала папка `ffmpeg/` portable-сборки
рядом с приложением, затем `PATH`. Так portable-архив работает без
установки ffmpeg в систему (критерии A10, A11).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


# since: v0.3 (FR-60, FR-61)
def _bundle_dir() -> Path:
    """Вернуть папку portable-сборки, если программа запущена из архива.

    Спека: FR-60, FR-62. Версия: v0.3.

    Определяет, что пакет лежит внутри собранного архива, и возвращает
    корень сборки. В исходниках возвращает корень репозитория, чтобы
    `ffmpeg/` искался и при запуске из рабочей копии.

    Returns:
        Путь к папке сборки.

    Raises:
        VideoTimerError: не бросает; при неудаче возвращается безопасный
            путь по умолчанию.
    """
    raise NotImplementedError


# since: v0.1 (FR-55, критерии A10, A11)
def find_ffmpeg() -> Path | None:
    """Найти исполняемый файл ffmpeg.

    Спека: FR-55, FR-60. Версия: v0.1.

    Args:
        Нет.

    Returns:
        Путь к ffmpeg или ``None``, если не найден. Отсутствие — не
        исключение: GUI должен открыться и объяснить, что делать (FR-55),
        поэтому решение принимает вызывающий код.

    Пример:
        find_ffmpeg()
        # Path("/usr/bin/ffmpeg")
    """
    for name in _PROGRAM_NAMES["ffmpeg"]:
        found = _which(name)
        if found:
            return Path(found)
    return None


# since: v0.1 (FR-11, FR-55)
def find_ffprobe() -> Path | None:
    """Найти исполняемый файл ffprobe.

    Спека: FR-11, FR-55. Версия: v0.1.

    Нужен для `Background.probe_duration()`. Ищется той же логикой, что и
    ffmpeg: сначала папка сборки, затем `PATH`. Если ffprobe нет, длительность
    просто остаётся неизвестной — рендер работает и без него.

    Returns:
        Путь к ffprobe или ``None``, если не найден.
    """
    for name in _PROGRAM_NAMES["ffprobe"]:
        found = _which(name)
        if found:
            return Path(found)
    return None


# since: v0.1 (FR-06, FR-11)
_PROGRAM_NAMES: dict[str, tuple[str, ...]] = {
    "ffmpeg": ("ffmpeg", "ffmpeg.exe"),
    "ffprobe": ("ffprobe", "ffprobe.exe"),
}
"""Имена исполняемых файлов: сначала без расширения, затем с `.exe` для Windows."""


# since: v0.1 (FR-55)
def _which(name: str) -> str:
    """Найти программу в `PATH`, отдельно от возможности подменить поиск в тестах.

    Спека: FR-55, FR-11. Версия: v0.1.

    Args:
        name: имя программы без пути.

    Returns:
        Полный путь к программе или пустая строка, если не найдена.
    """
    return shutil.which(name) or ""


# since: v0.1 (FR-06)
def default_font() -> Path | None:
    """Найти системный шрифт по умолчанию для `drawtext`.

    Спека: FR-06. Версия: v0.1 (системный шрифт), v0.3 (список шрифтов
    под Windows, macOS и Linux).

    Порядок проверки — общий для трёх систем: DejaVu Sans, Liberation Sans,
    Arial, Helvetica. На Windows проверяется `C:\\Windows\\Fonts`,
    на macOS — `/System/Library/Fonts`, на Linux — стандартные каталоги
    `/usr/share/fonts`. Возвращается первый существующий файл.

    Returns:
        Путь к файлу шрифта `.ttf` / `.otf` / `.ttc` или ``None``, если
        ничего не нашлось; тогда `FilterBuilder` сообщает пользователю, что
        задать свой шрифт (FR-06).

    Пример:
        default_font()
        # Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    """
    for directory in _font_dirs():
        if not directory.is_dir():
            continue
        for name in _FONT_NAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
        for name in _FONT_NAMES:
            for candidate in sorted(directory.rglob(name)):
                if candidate.is_file():
                    return candidate
    return None


# since: v0.1 (FR-06)
_FONT_NAMES: tuple[str, ...] = (
    "DejaVuSans.ttf",
    "LiberationSans-Regular.ttf",
    "arial.ttf",
    "Arial.ttf",
    "Helvetica.ttc",
)
"""Имена файлов шрифтов в порядке предпочтения, одинаковом для трёх систем."""


# since: v0.1 (FR-06)
def _font_dirs() -> tuple[Path, ...]:
    """Перечислить каталоги, где ищется системный шрифт.

    Спека: FR-06. Версия: v0.1.

    Порядок каталогов соответствует порядку систем в спецификации 7.6.
    Каталоги, которых нет в системе, всё равно возвращаются: проверка
    существования делается в :func:`default_font`.

    Returns:
        Кортеж путей к каталогам шрифтов.

    Пример:
        _font_dirs()
        # (Path("/usr/share/fonts"),)
    """
    return (
        Path("C:/Windows/Fonts"),
        Path("/System/Library/Fonts"),
        Path("/Library/Fonts"),
        Path("/usr/share/fonts"),
        Path("/usr/local/share/fonts"),
        Path.home() / ".fonts",
        Path.home() / ".local/share/fonts",
    )


# since: v0.1 (FR-20)
def available_h264_encoder() -> str | None:
    """Найти в этой сборке ffmpeg любой кодировщик H.264.

    Спека: FR-20. Версия: v0.1.

    Нужна тестам сборки цепочки фильтров и как страховка на время перехода
    между разными сборками ffmpeg: `libx264` есть не везде, и проверять таймер
    на устаревшем кодировщике бессмысленно — с ним кадр может и не собраться.

    Args:
        Нет.

    Returns:
        Имя кодировщика из :data:`_H264_FALLBACKS` либо ``None``, если в сборке
            ffmpeg нет ни одного.

    Пример:
        available_h264_encoder()
        # "libopenh264"
    """
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        return None

    finished = subprocess.run(
        [str(ffmpeg), "-hide_banner", "-encoders"], capture_output=True, text=True
    )
    if finished.returncode != 0:
        return None

    for line in finished.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] in _H264_FALLBACKS:
            return parts[1]
    return None


# since: v0.1 (FR-20)
_H264_FALLBACKS: tuple[str, ...] = (
    "libx264",
    "libopenh264",
    "h264_qsv",
    "h264_v4l2m2m",
    "h264_vaapi",
    "h264_nvenc",
    "h264_amf",
)
"""Кодировщики H.264 в порядке предпочтения, если основной недоступен."""


# since: v0.2 (FR-54)
def open_folder(path: Path) -> None:
    """Открыть папку в файловом менеджере системы.

    Спека: FR-54. Версия: v0.2 (кнопка «Открыть папку» после рендера).

    Кроссплатформенно: `explorer` на Windows, `open` на macOS, `xdg-open`
    на Linux. Команда собирается списком, `shell=True` не используется.

    Args:
        path: папка, которую нужно показать; если существует файл, открывается
            его папка.

    Returns:
        Ничего.

    Raises:
        VideoTimerError: `output: папка не найдена` — если `path` не
            существует; это состояние проверяется до кнопки, чтобы не
            показывать системную ошибку.
    """
    raise NotImplementedError
