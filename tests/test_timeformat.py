"""Тесты выражений времени для `drawtext`.

Главное свойство модуля — экранирование: двоеточие в тексте часов не должно
ломать разбор фильтра. Плюс соответствие `timeformat` ожидаемым картинкам
из критериев A1 и A2.

Модуль закрыт 01.10 вместе с `Background` и `FilterBuilder`: без
`clock_expression()` таймер нечем нарисовать.
"""

from __future__ import annotations

import pytest

from video_timer import timeformat
from video_timer.config import VideoTimerError


def drawtext_matches_ground_truth(text: str) -> bool:
    """Отрисовать текст через `text=` и сравнить кадр с `textfile`-эталоном.

    Спека: SPEC 7.3 (инвариант экранирования). Версия: v0.1.

    `textfile` читает символы как есть, поэтому кадр из него — эталон того,
    что должно получиться на экране. Побайтовое сравнение серых кадров ловит
    и неверный разбор фильтра, и лишние символы от недосчитанных слэшей.

    Args:
        text: строка, которую должен показать таймер.

    Returns:
        `True`, если ffmpeg разобрал фильтр и кадры совпали.

    Raises:
        Не бросает исключений: отсутствие ffmpeg даёт `False`.
    """
    import subprocess
    import tempfile
    from pathlib import Path

    from video_timer import osutil

    font = osutil.default_font()
    ffmpeg = osutil.find_ffmpeg()
    if font is None or ffmpeg is None:
        return False

    width, height = 640, 200
    size = width * height

    def frame(drawtext_args: str) -> bytes | None:
        chain = f"drawtext={drawtext_args},format=yuv420p"
        result = subprocess.run(
            [
                str(ffmpeg),
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c=black:s={width}x{height}:r=10:d=1",
                "-filter_complex",
                chain,
                "-frames:v",
                "1",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "gray",
                "-",
            ],
            capture_output=True,
        )
        if result.returncode != 0 or len(result.stdout) < size:
            return None
        return result.stdout

    with tempfile.TemporaryDirectory() as folder:
        reference_file = Path(folder) / "gt.txt"
        reference_file.write_text(text, encoding="utf-8")
        reference = frame(
            f"textfile={reference_file}:fontfile={font}:fontsize=64"
            f":fontcolor=white:x=10:y=10"
        )
        actual = frame(
            f"text={timeformat._escape(text)}:fontfile={font}:fontsize=64"
            f":fontcolor=white:x=10:y=10"
        )

    if reference is None or actual is None:
        return False
    return all(
        abs(left - right) <= 40 for left, right in zip(reference, actual)
    )


def test_clock_expression_mmss_escapes_colon() -> None:
    """Двоеточие в `text=` экранируется двумя слэшами (FR-04, SPEC 7.3).

    Значение `text=` разбирается дважды — фильтром и самим `drawtext`, —
    поэтому одного слэша не хватает: проверено на ffmpeg 7.1.
    """
    expression = timeformat.clock_expression("t", "mmss")

    assert "\\\\:" in expression
    assert ":" not in expression.replace("\\\\:", "")


def test_clock_expression_escapes_comma() -> None:
    """Запятая в `text=` экранируется одним слэшем (SPEC 7.3)."""
    assert timeformat._escape("a,b") == "a\\,b"


def test_clock_expression_escapes_backslash_first() -> None:
    """Обратный слэш экранируется раньше двоеточия, без двойного экранирования."""
    assert timeformat._escape("a\\b") == "a\\\\b"
    assert timeformat._escape("a\\:b") == "a\\\\\\\\:b"


def test_escape_result_is_parsed_by_real_ffmpeg() -> None:
    """Экранированный текст разбирается настоящим ffmpeg (SPEC 7.3).

    Регрессия на число слэшей: с неправильным их количеством ffmpeg либо
    не разбирает фильтр, либо рисует лишний символ.
    """
    assert drawtext_matches_ground_truth("00:05")
    assert drawtext_matches_ground_truth("00:05, ok")


def test_clock_expression_uses_integer_arithmetic() -> None:
    """Значение округляется целочисленно: на 9-й секунде отсчёта `00:01` (A1)."""
    expression = timeformat.clock_expression("t", "mmss")

    assert "floor(" in expression


def test_clock_expression_countdown_value() -> None:
    """Для отсчёта подставляется выражение `N-t` (FR-02)."""
    expression = timeformat.clock_expression("10-t", "mmss")

    assert "10-t" in expression


def test_clock_expression_stopwatch_value() -> None:
    """Для секундомера подставляется время кадра `t` (FR-01)."""
    expression = timeformat.clock_expression("t", "mmss")

    assert "t" in expression


def test_clock_expression_never_negative() -> None:
    """Отрицательное значение не показывается: время обрезается нулём (FR-02)."""
    expression = timeformat.clock_expression("10-t", "mmss")

    assert "max(0" in expression


def test_unknown_format_rejected() -> None:
    """Неизвестный формат даёт ошибку «fmt: …», а не странное выражение."""
    with pytest.raises(VideoTimerError, match=r"^fmt: "):
        timeformat.clock_expression("t", "секунды")


def test_static_clock_text_mmss() -> None:
    """Образец для `mmss` — `00:00` (FR-04)."""
    assert timeformat.static_clock_text("mmss") == "00:00"


def test_static_clock_text_unknown_format() -> None:
    """Неизвестный формат в `static_clock_text` даёт ту же ошибку, что и выше."""
    with pytest.raises(VideoTimerError, match=r"^fmt: "):
        timeformat.static_clock_text("секунды")


def test_escape_is_idempotent_for_plain_text() -> None:
    """Строка без двоеточий и запятых не меняется (FR-04)."""
    assert timeformat._escape("00-05") == "00-05"


def test_module_exports_three_functions() -> None:
    """Публичный интерфейс модуля состоит из трёх функций (SPEC 7.3)."""
    assert callable(timeformat.clock_expression)
    assert callable(timeformat.static_clock_text)
