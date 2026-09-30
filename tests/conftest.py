"""Общие фикстуры тестов.

Фикстуры реализованы вместе с `TimerConfig.validate()` (30.09, критерий A7):
тесты конфигурации могут собирать минимальный корректный рендер и менять в
нём одно поле, не завися от ffmpeg.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from video_timer.config import TimerConfig


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
