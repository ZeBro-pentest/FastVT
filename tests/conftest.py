"""Общие фикстуры тестов.

На этапе каркаса (SDD, этап 3) фикстуры объявлены, но не реализованы:
тесты красные, а не пропущенные. Реализуются вместе с кодом по критериям
приёмки из `specs/v0.1.md`.
"""

from __future__ import annotations

from pathlib import Path

import pytest


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
        NotImplementedError: фикстура-заготовка, тело появится вместе с
            реализацией рендера.
    """
    raise NotImplementedError("не реализовано: фикстура tmp_output")


@pytest.fixture
def base_cfg(tmp_output: Path):
    """Вернуть минимальную корректную конфигурацию для рендера.

    Спека: критерии A1, A2, FR-40. Версия: v0.1.

    Ожидаемое состояние: сплошной чёрный фон, секундомер, разрешение
    `1280x720`, `30` fps, выход — `tmp_output`. От неё отталкиваются тесты
    ошибок, меняя одно поле.

    Args:
        tmp_output: путь выходного файла из фикстуры выше.

    Returns:
        `TimerConfig`, который проходит `TimerConfig.validate()`.

    Raises:
        NotImplementedError: фикстура-заготовка, тело появится вместе с
            `TimerConfig`.
    """
    raise NotImplementedError("не реализовано: фикстура base_cfg")
