"""Общие фикстуры тестов.

Фикстуры реализованы вместе с `TimerConfig.validate()` (30.09, критерий A7):
тесты конфигурации могут собирать минимальный корректный рендер и менять в
нём одно поле, не завися от ffmpeg.

Здесь же помощники для тестов, которые зовут настоящий ffmpeg: они читают
кадры и сравнивают их с эталоном, отрисованным через `drawtext` из файла.
Так проверяется не разбор фильтра, а то, что пользователь увидит на экране.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from video_timer import osutil
from video_timer.config import TimerConfig

FRAME_WIDTH = 320
FRAME_HEIGHT = 240
"""Размер кадра для тестов с настоящим ffmpeg: маленький, но читаемый."""

RAW_PLANE = FRAME_WIDTH * FRAME_HEIGHT
"""Размер одного кадра в байтах для `gray`."""


@pytest.fixture
def tmp_output(tmp_path: Path) -> Path:
    """Вернуть путь для выходного файла во временной папке.

    Спека: критерии A1, A2. Версия: v0.1.

    Тесты рендера пишут результат в `tmp_path`, а не в репозиторий, чтобы
    прогон pytest не оставлял файлов и не зависел от прав на запись.

    Args:
        tmp_path: временная папка, которую создаёт pytest.

    Returns:
        Путь к несуществующему файлу `.mp4` внутри `tmp_path`.

    Raises:
        Не бросает исключений.
    """
    return tmp_path / "out.mp4"


@pytest.fixture
def base_cfg(tmp_output: Path) -> TimerConfig:
    """Вернуть минимальную корректную конфигурацию для рендера.

    Спека: критерии A1, A2, FR-40. Версия: v0.1.

    Состояние: сплошной чёрный фон, секундомер, `duration` задан (обязателен
    для секундомера без видео-фона, FR-12), выход — `tmp_output`. От неё
    отталкиваются тесты ошибок, меняя одно поле.

    Args:
        tmp_output: путь выходного файла из фикстуры выше.

    Returns:
        `TimerConfig`, который проходит `TimerConfig.validate()`.

    Raises:
        Не бросает исключений.
    """
    return TimerConfig(output=tmp_output, duration=8.0)


def ffmpeg_or_skip() -> tuple[str, str]:
    """Вернуть пути к ffmpeg и системному шрифту либо пропустить тест.

    Спека: критерии A1, A2. Версия: v0.1.

    Тесты с настоящим рендером бессмысленны без ffmpeg и шрифта: падать на
    отсутствии программы нельзя (FR-55), а молча пропускать проверку врёт, поэтому
    вызывающий код решает сам.

    Returns:
        Пару `(путь к ffmpeg, путь к шрифту)`.

    Raises:
        pytest.skip.Exception: если ffmpeg или системный шрифт не найдены.
    """
    ffmpeg = osutil.find_ffmpeg()
    if ffmpeg is None:
        pytest.skip("ffmpeg не найден")
    font = osutil.default_font()
    if font is None:
        pytest.skip("системный шрифт не найден")
    return str(ffmpeg), str(font)


def read_frame_gray(
    ffmpeg: str, source_args: list[str]
) -> bytes | None:
    """Прочитать один кадр в оттенках серого.

    Спека: критерии A1, A2. Версия: v0.1.

    Args:
        ffmpeg: путь к исполняемому файлу ffmpeg.
        source_args: аргументы до `-frames:v`, например `["-ss", "9", "-i", "out.mp4"]`.

    Returns:
        Байты кадра размером :data:`RAW_PLANE` или ``None``, если ffmpeg
            ничего не выдал.

    Raises:
        Не бросает исключений.
    """
    command = [
        ffmpeg,
        "-v",
        "error",
        *source_args,
        "-frames:v",
        "1",
        "-f",
        "rawvideo",
        "-pix_fmt",
        "gray",
        "-",
    ]
    finished = subprocess.run(command, capture_output=True)
    if len(finished.stdout) < RAW_PLANE:
        return None
    return finished.stdout


def frames_match(
    left: bytes | None, right: bytes | None, tolerance: int = 60
) -> bool:
    """Сравнить два кадра с допуском на сжатие видео.

    Спека: критерии A1, A2. Версия: v0.1.

    Кадры проходят через кодек, поэтому пиксели у краёв букв отличаются на
    несколько единиц. Допуск 60 отсекает такую разницу и оставляет настоящее
    расхождение — другой текст или другая позиция.

    Args:
        left: первый кадр.
        right: второй кадр.
        tolerance: допустимое отличие яркости одного пикселя.

    Returns:
        `True`, если кадры различаются не более чем на 300 пикселей.

    Raises:
        Не бросает исключений.
    """
    if left is None or right is None:
        return False
    if len(left) != len(right):
        return False
    differing = 0
    for index in range(RAW_PLANE):
        if abs(left[index] - right[index]) > tolerance:
            differing += 1
            if differing >= 300:
                return False
    return True


def drawtext_reference(
    ffmpeg: str,
    font: str,
    text: str,
    output: Path,
    color: str = "white",
    font_size: int = 48,
) -> bytes | None:
    """Отрисовать текст из файла и вернуть кадр как эталон.

    Спека: критерии A1, A2, инвариант SPEC 7.3. Версия: v0.1.

    `drawtext` с `textfile` читает символы как есть, без всякого экранирования,
    поэтому такой кадр — точная картинка того, что должен показать таймер.
    Разрешение, размер шрифта и положение обязаны совпадать с рендером,
    иначе сравнивать нечего.

    Args:
        ffmpeg: путь к исполняемому файлу ffmpeg.
        font: путь к файлу шрифта.
        text: строка-эталон, например ``00:01``.
        output: путь для промежуточного кадра.
        color: цвет текста эталона.
        font_size: размер шрифта, должен совпадать с конфигурацией рендера.

    Returns:
        Байты кадра с текстом или ``None``, если ffmpeg не отдал кадр.

    Raises:
        Не бросает исключений.
    """
    text_file = output.with_suffix(".txt")
    text_file.write_text(text, encoding="utf-8")
    chain = (
        f"drawtext=textfile={text_file}:fontfile={font}:fontsize={font_size}"
        f":fontcolor={color}:x=w-tw-40:y=h-th-40,format=yuv420p"
    )
    command = [
        ffmpeg,
        "-v",
        "error",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=black:s={FRAME_WIDTH}x{FRAME_HEIGHT}:r=30:d=1",
        "-filter_complex",
        chain,
        "-frames:v",
        "1",
        str(output),
    ]
    subprocess.run(command, capture_output=True)
    if not output.exists():
        return None
    return read_frame_gray(ffmpeg, ["-i", str(output)])
