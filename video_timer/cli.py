"""Командный интерфейс: разбор аргументов, запуск рендера, коды возврата.

Модуль переводит параметры командной строки в `TimerConfig` и вызывает
`render()`. Зависимости: `config`, `renderer`, `estimate`, `osutil`.
`gui` этот модуль не импортирует и наоборот.

Коды возврата (SPEC 7.8):
    - 0 — успех
    - 1 — ошибка валидации или рендера
    - 2 — неверные аргументы командной строки
"""

from __future__ import annotations

import argparse
from pathlib import Path

from video_timer import __version__
from video_timer.config import TimerConfig


# since: v0.1 (FR-50), `--estimate-only` и `--verbose` — v0.2
def build_parser() -> argparse.ArgumentParser:
    """Собрать парсер аргументов командной строки.

    Спека: FR-50. Версия: v0.1 (параметры из `specs/v0.1.md`), v0.2
    (`--estimate-only`, `--verbose`, `--encoder`, `--crf`, `--preset`).

    Имена опций совпадают с именами полей `TimerConfig` через дефис,
    чтобы сообщение об ошибке и подсказка `--help` говорили одно и то же:
    `font-size` в справке означает `font_size` в конфигурации (FR-41).
    Все подписи и тексты справки — на русском (NFR-08).

    Returns:
        Готовый `argparse.ArgumentParser`.

    Пример:
        args = build_parser().parse_args(["-o", "out.mp4", "--mode", "countdown"])
        args.mode
        # "countdown"
    """
    raise NotImplementedError


# since: v0.1 (FR-50)
def main(argv: list[str] | None = None) -> int:
    """Точка входа CLI: разобрать аргументы, отрендерить, вернуть код.

    Спека: FR-42, FR-50. Версия: v0.1 (рендер), v0.2 (`--estimate-only`,
    `--verbose`).

    Все сообщения об ошибках печатаются в `stderr` без трейсбека (FR-42);
    пользователь видит только «поле: что не так». `--help` и `--version`
    обрабатываются `argparse` и дают код 0.

    Args:
        argv: аргументы командной строки; ``None`` — читаются из `sys.argv`.

    Returns:
        0 при успехе, 1 при ошибке валидации или рендера, 2 при неверных
        аргументах.

    Пример:
        python -m video_timer.cli -o out.mp4 --mode countdown --countdown-seconds 10
    """
    raise NotImplementedError


# since: v0.1 (FR-50)
def _config_from_args(args: argparse.Namespace) -> TimerConfig:
    """Преобразовать разобранные аргументы в `TimerConfig`.

    Спека: FR-50. Версия: v0.1.

    Единственное место, где строки превращаются в типы: `Path`, `int`,
    `float`. Приведения типов заданы в `build_parser()`, здесь остаётся
    только сборка объекта и приведение `background` к `Path | None`.

    Args:
        args: результат `build_parser().parse_args()`.

    Returns:
        Готовую конфигурацию без вызова `validate()` — проверка остаётся
        за `render()` (FR-40).

    Raises:
        VideoTimerError: не бросает; неверные типы отсеивает argparse,
            семантику — `TimerConfig.validate()`.
    """
    raise NotImplementedError


if __name__ == "__main__":  # pragma: no cover - точка входа CLI (FR-50)
    raise SystemExit(main())
