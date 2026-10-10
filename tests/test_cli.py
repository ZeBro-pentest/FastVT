"""Тесты командного интерфейса.

Коды возврата (SPEC 7.8): 0 — успех, 1 — ошибка валидации или рендера,
2 — неверные аргументы. Сценарий A7 проверяется через CLI: код 1 и
сообщение с префиксом имени поля, ffmpeg при этом не запускался.
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys
from pathlib import Path

import pytest

from video_timer import cli, osutil
from video_timer.cli import _config_from_args, build_parser, main
from video_timer.config import TimerConfig, VideoTimerError


@pytest.fixture
def h264(monkeypatch: pytest.MonkeyPatch) -> str:
    """Собрать тестовые ролики тем кодировщиком H.264, что есть в системе.

    Спека: FR-20. Версия: v0.1.

    `resolved_encoder()` в v0.1 возвращает константу `libx264` (FR-20), а
    проверка доступности кодека — только FR-22 в v0.2. В сборках ffmpeg
    без libx264 ролик собрать нельзя, при этом корректность CLI от кодека
    не зависит, поэтому подменяется только `resolved_encoder()`: проверяются
    коды возврата и разбор аргументов, а не выбор кодека.

    Args:
        monkeypatch: фикстура pytest для временной подмены метода.

    Returns:
        Имя кодировщика, которым будет записан тестовый ролик.

    Raises:
        pytest.skip.Exception: если ffmpeg не найден либо в сборке нет
            ни одного кодировщика H.264.
    """
    name = osutil.available_h264_encoder()
    if name is None:
        pytest.skip("в сборке ffmpeg нет кодировщика H.264")
    if name != "libx264":
        monkeypatch.setattr(TimerConfig, "resolved_encoder", lambda self: name)
    return name


def test_countdown_default_matches_config_and_spec() -> None:
    """Без `--countdown-seconds` отсчёт идёт 60 с, как в `TimerConfig` и спеке.

    Спека: FR-02, FR-50. Версия: v0.1.

    Умолчание CLI не должно расходиться с таблицей параметров
    `specs/v0.1.md` и с полем `TimerConfig.countdown_seconds`: иначе одна и
    та же команда из CLI и из GUI делает ролики разной длительности. При
    `countdown_seconds=60` и `hold_seconds=5` результат длится 65 с (FR-12).
    """
    spec_default = TimerConfig(output=Path("out.mp4")).countdown_seconds
    cfg = _config_from_args(
        build_parser().parse_args(["-o", "out.mp4", "--mode", "countdown"])
    )

    assert spec_default == 60.0
    assert cfg.countdown_seconds == spec_default
    assert cfg.known_total_duration() == 65.0


def test_a7_exit_code_1_on_font_size_zero(
    capsys: pytest.CaptureFixture, tmp_path: Path
) -> None:
    """A7: `font-size 0` даёт код возврата 1, а не 0 и не 2."""
    code = main(["-o", str(tmp_path / "out.mp4"), "--duration", "8", "--font-size", "0"])

    assert code == 1


def test_a7_message_starts_with_field_name(
    capsys: pytest.CaptureFixture, tmp_path: Path
) -> None:
    """A7: в `stderr` есть сообщение, начинающееся с `font-size: `."""
    main(["-o", str(tmp_path / "out.mp4"), "--duration", "8", "--font-size", "0"])
    captured = capsys.readouterr()

    assert captured.err.startswith("font-size: ")
    assert captured.out == ""


def test_a7_no_traceback_in_output(
    capsys: pytest.CaptureFixture, tmp_path: Path
) -> None:
    """A7: в выводе нет трейсбека (FR-42)."""
    main(["-o", str(tmp_path / "out.mp4"), "--duration", "8", "--font-size", "0"])
    captured = capsys.readouterr()

    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out
    assert 'File "' not in captured.err


def test_a7_ffmpeg_not_launched(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A7: ffmpeg не запускался — процесс не создавался при ошибке валидации."""
    started: list[object] = []

    def _record(*args: object, **kwargs: object) -> object:
        started.append(args)
        raise AssertionError("ffmpeg не должен запускаться до проверки полей")

    monkeypatch.setattr("video_timer.renderer.subprocess.Popen", _record)
    code = main(["-o", str(tmp_path / "out.mp4"), "--duration", "8", "--font-size", "0"])

    assert code == 1
    assert started == []


def test_spec_example_command_succeeds(tmp_path: Path, h264: str) -> None:
    """Пример из `specs/v0.1.md` отсчитывает 10 с и завершается кодом 0."""
    output = tmp_path / "out.mp4"
    code = main(
        ["-o", str(output), "--mode", "countdown", "--countdown-seconds", "10"]
    )

    assert code == 0
    assert output.is_file()


def test_success_returns_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture, h264: str
) -> None:
    """Успешный рендер даёт код возврата 0 и печатает путь результата."""
    output = tmp_path / "out.mp4"
    code = main(["-o", str(output), "--duration", "8"])
    captured = capsys.readouterr()

    assert code == 0
    assert output.is_file()
    assert str(output) in captured.out


def test_render_error_returns_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture, tmp_path: Path
) -> None:
    """Ошибка рендера даёт код 1 и понятный текст без лога ffmpeg (FR-42)."""
    def _render(cfg: object, on_progress: object = None) -> None:
        raise VideoTimerError(
            "render: ffmpeg завершился с ошибкой\n"
            "ffmpeg version 7.1.5 — вот этот баннер в лог попадать не должен\n"
            "Unknown encoder 'h265'"
        )

    monkeypatch.setattr(cli, "render", _render)
    code = main(["-o", str(tmp_path / "out.mp4"), "--duration", "8"])
    captured = capsys.readouterr()

    assert code == 1
    assert captured.err.startswith("render: ")
    assert "Traceback" not in captured.err


def test_unknown_argument_returns_two(capsys: pytest.CaptureFixture) -> None:
    """Неизвестная опция даёт код 2 — это ошибка разбора, не валидации."""
    code = main(["-o", "out.mp4", "--no-such-option"])

    assert code == 2


def test_missing_output_option_returns_two(capsys: pytest.CaptureFixture) -> None:
    """Без обязательной `-o` argparse завершает работу с кодом 2."""
    code = main([])

    assert code == 2


def test_help_returns_zero(capsys: pytest.CaptureFixture) -> None:
    """`--help` показывает справку на русском и завершает работу с кодом 0."""
    code = main(["--help"])
    captured = capsys.readouterr()

    assert code == 0
    assert "Генератор видео-таймера" in captured.out
    assert "-o, --output ПУТЬ" in captured.out
    assert "(обязателен)" in captured.out
    assert "параметры" in captured.out
    assert "show this help message" not in captured.out
    assert "show program's version" not in captured.out


def test_parser_option_names_match_config_fields() -> None:
    """Имя опции с дефисом соответствует полю конфигурации (FR-41)."""
    parser = build_parser()
    fields = {field.name for field in dataclasses.fields(TimerConfig)}
    checked = 0

    for action in parser._actions:
        if action.dest in ("help", "version"):
            continue
        assert action.dest in fields, (
            f"опция --{action.dest.replace('_', '-')} не имеет поля в TimerConfig"
        )
        checked += 1

    assert checked >= 12


def test_parser_accepts_video_background(tmp_path: Path) -> None:
    """Опция `-b` принимает путь к видеофайлу (FR-10)."""
    video = tmp_path / "source.mp4"
    video.write_bytes(b"")
    args = build_parser().parse_args(["-o", "out.mp4", "-b", str(video)])

    assert args.background == str(video)
    assert _config_from_args(args).background == video


def test_parser_accepts_resolution_and_fit(tmp_path: Path) -> None:
    """Опции `--resolution` и `--fit` доходят до конфигурации (FR-13, FR-14)."""
    args = build_parser().parse_args(
        ["-o", "out.mp4", "--resolution", "1080x1080", "--fit", "cover"]
    )
    cfg = _config_from_args(args)

    assert cfg.resolution == "1080x1080"
    assert cfg.fit == "cover"


def test_parser_fit_defaults_to_contain() -> None:
    """Без `--fit` используется `contain`, как в `TimerConfig` (FR-14)."""
    cfg = _config_from_args(build_parser().parse_args(["-o", "out.mp4"]))

    assert cfg.fit == "contain"
    assert cfg.resolution is None


def test_parser_rejects_bad_fit(capsys: pytest.CaptureFixture) -> None:
    """Недопустимый `--fit` отклоняется argparse (FR-14)."""
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["-o", "out.mp4", "--fit", "fill"])

    assert excinfo.value.code == 2


def test_parser_rejects_bad_choice(capsys: pytest.CaptureFixture) -> None:
    """Недопустимый выбор для `--mode` отклоняется argparse (FR-01)."""
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["-o", "out.mp4", "--mode", "blink"])

    assert excinfo.value.code == 2


def test_main_accepts_argv_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """`main(argv)` работает со списком аргументов без `sys.argv` (SPEC 7.8)."""
    monkeypatch.setattr(sys, "argv", ["prog", "--no-such-option"])
    code = main(["--help"])

    assert code == 0


def test_parser_is_reusable() -> None:
    """`build_parser()` создаёт новый парсер, а не общий изменяемый (SPEC 7.8)."""
    first = build_parser()
    second = build_parser()

    assert first is not second
    assert first.parse_args(["-o", "a.mp4"]).output == "a.mp4"
    assert second.parse_args(["-o", "b.mp4"]).output == "b.mp4"


def test_cli_reports_estimate_only() -> None:
    """Опция `--estimate-only` печатает оценку без кодирования (v0.2, A8)."""
    pytest.fail("не реализовано: A8 — --estimate-only без запуска кодирования")


def test_module_exports_entry_points() -> None:
    """Модуль объявляет `build_parser()`, `main()` и точку входа (SPEC 7.8)."""
    assert callable(cli.build_parser)
    assert callable(cli.main)

    finished = subprocess.run(
        [sys.executable, "-m", "video_timer.cli", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert finished.returncode == 0
    assert "Генератор видео-таймера" in finished.stdout
