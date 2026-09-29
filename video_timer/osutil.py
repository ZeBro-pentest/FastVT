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
    raise NotImplementedError


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
    raise NotImplementedError


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
    raise NotImplementedError


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
