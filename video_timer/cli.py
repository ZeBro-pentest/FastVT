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
import sys
from pathlib import Path

from video_timer import __version__
from video_timer.config import TimerConfig, VideoTimerError
from video_timer.renderer import render


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
    parser = argparse.ArgumentParser(
        prog="video_timer.cli",
        description="Генератор видео-таймера для наложения секундомера или обратного отсчёта",
        formatter_class=argparse.RawTextHelpFormatter,
        add_help=False,
    )
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        help="Показать эту справку и завершить работу",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        required=True,
        metavar="ПУТЬ",
        help="Путь к выходному MP4 (обязателен)",
    )
    parser.add_argument(
        "--mode",
        choices=["stopwatch", "countdown"],
        default="stopwatch",
        help="Режим: stopwatch или countdown (по умолчанию stopwatch)",
    )
    parser.add_argument(
        "-b",
        "--background",
        type=str,
        default=None,
        help="Фон: сплошной цвет или путь к видео/картинке (опц.)",
    )
    parser.add_argument(
        "--bg-color",
        dest="bg_color",
        type=str,
        default="black",
        help="Цвет фона, если не задано видео",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Длительность рендера в секундах (опц.)",
    )
    parser.add_argument(
        "--position",
        type=str,
        default="br",
        help="Позиция таймера (по умолчанию br)",
    )
    parser.add_argument(
        "--font-size",
        dest="font_size",
        type=int,
        default=64,
        help="Размер шрифта",
    )
    parser.add_argument(
        "--color",
        type=str,
        default="white",
        help="Цвет текста",
    )
    parser.add_argument(
        "--countdown-seconds",
        dest="countdown_seconds",
        type=float,
        default=60.0,
        help="Длительность обратного отсчёта в секундах (по умолчанию 60)",
    )
    parser.add_argument(
        "--hold-seconds",
        dest="hold_seconds",
        type=float,
        default=5.0,
        help="Длительность hold-паузы",
    )
    parser.add_argument(
        "--hold-color",
        dest="hold_color",
        type=str,
        default="#e6362c",
        help="Цвет текста в hold-паузе",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=30,
        help="Частота кадров",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
        help="Показать номер версии и завершить работу",
    )
    # Заголовок группы опций argparse по умолчанию английский; менять его
    # можно только через приватный атрибут группы. Текст справки должен быть
    # целиком на русском, как и остальные тексты интерфейса (NFR-08).
    parser._optionals.title = "параметры"
    return parser


def _config_from_args(args: argparse.Namespace) -> TimerConfig:
    """Преобразовать разобранные аргументы в `TimerConfig`.

    Спека: FR-50. Версия: v0.1.

    Значения опций, не переданные пользователем, берутся из `TimerConfig`:
    аргументы `default=` в `build_parser()` и `getattr`-подстановки здесь
    обязаны совпадать с полями конфигурации, иначе одна и та же команда
    из CLI и из GUI даст разный результат.

    Args:
        args: пространство имён из `build_parser().parse_args()`.

    Returns:
        Готовую конфигурацию; она ещё не проверена — проверку делает `render()`.

    Raises:
        Не бросает исключений: неверные значения сообщает
        `TimerConfig.validate()` в формате «поле: что не так» (FR-41).
    """
    background: Path | None = None
    if getattr(args, "background", None):
        background = Path(args.background)

    return TimerConfig(
        output=Path(args.output),
        mode=args.mode,
        background=background,
        bg_color=args.bg_color,
        duration=getattr(args, "duration", None),
        position=args.position,
        font_size=args.font_size,
        color=args.color,
        countdown_seconds=getattr(args, "countdown_seconds", 60.0),
        hold_seconds=getattr(args, "hold_seconds", 5.0),
        hold_color=args.hold_color,
        fps=args.fps,
    )


def main(argv: list[str] | None = None) -> int:
    """Точка входа CLI: разобрать аргументы, отрендерить, вернуть код.

    Спека: FR-40, FR-41, FR-42, FR-50. Версия: v0.1. Коды возврата —
    SPEC 7.8.

    Порядок работы: сначала argparse, потом `TimerConfig.validate()` внутри
    `render()`, потом запуск ffmpeg. Поэтому ошибка в поле даёт код 1 с
    сообщением `«поле: что не так»`, а не запуск фильтров (критерий A7).
    Трейсбек и сырой лог ffmpeg наружу не идут (FR-42): пользователь видит
    только текст `VideoTimerError`.

    Args:
        argv: список аргументов без имени программы, например
            ``["-o", "out.mp4", "--duration", "8"]``; ``None`` — взять
            `sys.argv[1:]`. Список удобен тестам: они не трогают глобальное
            состояние интерпретатора.

    Returns:
        0 — ролик записан; 1 — ошибка валидации или рендера; 2 — неверные
        аргументы командной строки.

    Raises:
        Не бросает исключений: любая ошибка переводится в код возврата и
        короткое сообщение в `stderr`, `KeyboardInterrupt` не перехватывается.

    Пример:
        main(["-o", "out.mp4", "--mode", "countdown", "--countdown-seconds", "10"])
        # 0
    """
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exit_error:
        if exit_error.code not in (0, 1, 2):
            return 2
        return exit_error.code
    except Exception:
        return 2

    try:
        cfg = _config_from_args(args)
        result = render(cfg)
    except VideoTimerError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1

    print(str(result.output))
    return 0


if __name__ == "__main__":  # pragma: no cover - точка входа CLI (FR-50)
    raise SystemExit(main())
