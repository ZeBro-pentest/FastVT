"""Запуск ffmpeg: сборка команды, прогресс, отмена, понятные ошибки.

Модуль — верхний уровень движка: `cli` и `gui` вызывают `render()`, тот
создаёт `FFmpegRenderer`. Зависимости: `config`, `background`, `filters`,
`encoders`, `osutil`. Покадровой обработки в Python нет (NFR-02) — вся
работа с видео внутри ffmpeg.

Два правила, важные для интерфейса:
    - лог ffmpeg читается потоком, в памяти держится не более 50 последних
      строк (NFR-04), наружу отдаётся только этот хвост
    - пользователю возвращается `VideoTimerError` с коротким текстом, а не
      трейсбек и не сырой лог (FR-42)
"""

from __future__ import annotations

import subprocess
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from video_timer import osutil
from video_timer.background import Background
from video_timer.config import TimerConfig, VideoTimerError
from video_timer.encoders import OUTPUT_CODECS
from video_timer.filters import FilterBuilder

# since: v0.1 (NFR-04)
LOG_TAIL_LINES: int = 50
"""Сколько последних строк лога ffmpeg хранятся в памяти (NFR-04)."""

# since: v0.1 (NFR-05)
_STOP_TIMEOUT_SECONDS: float = 5.0
"""Сколько ждать завершения ffmpeg после `terminate()`, прежде чем убить (NFR-05)."""

# since: v0.1 (FR-42, NFR-04)
_MAX_LOG_LINES: int = 5
"""Сколько последних строк лога ffmpeg попадает в сообщение об ошибке (FR-42).

Причина ошибки всегда в самом конце: ffmpeg печатает её последней строкой.
Брать больше строк нельзя — выше лежит баннер со списком кодеков на
несколько тысяч символов, и в сообщении вместо ошибки пользователь увидит
перечень возможностей сборки. Полный хвост остаётся в `RenderResult.tail_log`.
"""

# since: v0.1 (FR-42, NFR-04)
_MAX_LOG_CHARS: int = 500
"""Предел длины текста, который дописывается в сообщение об ошибке (FR-42).

Последние строки могут быть длинными путями или названиями параметров;
сообщение в GUI должно помещаться в несколько строк статуса.
"""

# since: v0.1 (FR-20)
_X264: str = "libx264"
"""Кодек, для которого в команде добавляются CRF и preset (FR-20, FR-23)."""


@dataclass
class RenderResult:
    """Результат успешного рендера.

    Спека: FR-42, FR-51. Версия: v0.1.

    Attributes:
        output: путь записанного файла.
        duration_seconds: длительность результата, если её удалось узнать
            из вывода ffmpeg; ``None`` — если не удалось, это не ошибка.
        tail_log: не более 50 последних строк лога ffmpeg для диагностики
            (NFR-04); показывается в GUI пользователю не целиком.
    """

    output: Path
    duration_seconds: float | None
    tail_log: str


# since: v0.2 (FR-51)
class RenderCancelled(VideoTimerError):
    """Рендер остановлен по требованию пользователя.

    Спека: FR-51. Версия: v0.2.

    Отдельный класс, чтобы GUI отличил отмену от ошибки: не показывать
    красное сообщение, а просто возвращает панель в исходное состояние.
    """


# since: v0.1 (FR-20, FR-51, FR-42)
class FFmpegRenderer:
    """Сборка и запуск одной команды ffmpeg.

    Спека: FR-11, FR-12, FR-13, FR-14, FR-15, FR-20, FR-23, FR-51. Версия: v0.1
    (запуск и прогресс), v0.2 (отмена, звук, качество).

    Экземпляр привязан к одной конфигурации и к одному запуску. `run()`
    можно вызвать один раз; повторный вызов на том же экземпляре не
    предусмотрен. Отмена из другого потока безопасна: `cancel()` только
    ставит флаг и завершает процесс, не трогая состояние GUI.

    Args:
        cfg: конфигурация рендера, уже проверенная `TimerConfig.validate()`.
    """

    def __init__(self, cfg: TimerConfig) -> None:
        """Запомнить конфигурацию и найти исполняемый файл ffmpeg.

        Спека: FR-55. Версия: v0.1.

        ffmpeg ищется при создании объекта, а не при запуске: без него
        рендер всё равно невозможен, а GUI должен показать сообщение сразу
        при нажатии «Рендерить», а не через несколько секунд ожидания.

        Args:
            cfg: конфигурация рендера.

        Raises:
            VideoTimerError: `ffmpeg: не найден в системе` — если ffmpeg нет
                ни в папке portable-сборки, ни в `PATH`; текст содержит
                инструкцию по установке (FR-55).
        """
        ffmpeg = osutil.find_ffmpeg()
        if ffmpeg is None:
            raise VideoTimerError(
                "ffmpeg: не найден в системе. Установите ffmpeg "
                "и перезапустите программу"
            )
        self.cfg = cfg
        self.ffmpeg = ffmpeg
        self.background = Background(cfg)
        self.filters = FilterBuilder(cfg, self.background)
        self._cancelled = False
        self._process: subprocess.Popen[str] | None = None

    # since: v0.1 (FR-13, FR-20, FR-23)
    def build_command(self) -> list[str]:
        """Собрать полный список аргументов ffmpeg для этой конфигурации.

        Спека: FR-11…FR-15, FR-20, FR-23. Версия: v0.1 (видео, цвет),
        v0.2 (картинка, звук).

        Собирается список строк, `shell=True` не используется: пути с
        пробелами и кавычками остаются целыми аргументами. Структура:
            1. ``-y`` — перезаписать выходной файл без вопроса
            2. входные аргументы из `Background.input_args()`
            3. ``-filter_complex`` из `FilterBuilder.build()`
            4. кодек видео из `TimerConfig.resolved_encoder()`, CRF и preset
               для libx264 (FR-20, FR-23)
            5. аудиокодек и `-map 0:a:0`, только если фон звуковой (FR-15)
            6. ``-r`` с `cfg.fps`, путь выхода

        Звук переносится из видео-фона как есть и перекодируется в кодек
        контейнера по :data:`encoders.OUTPUT_CODECS` (FR-15). У цвета и
        картинки, а также если ffprobe не нашёл аудио, `-map` не добавляется:
        иначе ffmpeg падает на пустом потоке. Без `-map` звук молчаливого
        фона просто не попадает в вывод.

        CRF и preset добавляются только для libx264: у других кодеков таких
        опций нет, и ffmpeg отверг бы команду целиком.

        Returns:
            Список аргументов, готовый для `subprocess.Popen`.

        Raises:
            VideoTimerError: если фон недоступен или не собирается цепочка
            фильтров, например не найден шрифт (FR-06).

        Пример:
            cmd = FFmpegRenderer(cfg).build_command()
            # ["ffmpeg", "-y", "-f", "lavfi", "-i", "color=...", ...]
        """
        encoder = self.cfg.resolved_encoder()
        command = [
            str(self.ffmpeg),
            "-y",
            *self.background.input_args(),
            "-filter_complex",
            ",".join(self.filters.build()),
            "-c:v",
            encoder,
        ]
        if encoder == _X264:
            command.extend(
                ["-crf", str(self.cfg.crf), "-preset", self.cfg.preset]
            )
        if self.background.has_audio():
            audio_codec = OUTPUT_CODECS.get(
                self.cfg.output.suffix.lower(), {}
            ).get("audio")
            if audio_codec is not None:
                command.extend(["-map", "0:a:0", "-c:a", audio_codec])
        command.extend(["-r", str(self.cfg.fps), str(self.cfg.output)])
        return command

    # since: v0.1 (FR-51, NFR-04, NFR-05)
    def run(
        self, on_progress: Callable[[float, float | None], None] | None = None
    ) -> RenderResult:
        """Запустить ffmpeg и дождаться завершения, отдавая прогресс.

        Спека: FR-51, NFR-02, NFR-04, FR-42, FR-41. Версия: v0.1 (прогресс,
        папка результата), v0.2 (отмена).

        Поток ffmpeg читается построчно, а не через `communicate()`: иначе
        длинный лог съедает память, а прогрессбар не двигается. Хранится
        не более :data:`LOG_TAIL_LINES` последних строк.

        Поток с `-progress pipe:2` разбирается построчно, из строк `out_time_us`
        и `progress` считается доля прогресса. Если общая длительность
        неизвестна, второй аргумент колбэка равен ``None`` — GUI покажет
        неопределённый индикатор.

        Перед запуском создаётся папка результата (`FR-41`): пользователь
        вводит путь и получает файл там, куда попросил, вместо сообщения
        про ffmpeg.

        Args:
            on_progress: колбэк ``(доля_0..1, всего_секунд)``, вызывается в
                цикле чтения лога; ``None`` — прогресс не нужен. Вызывается
                из этого потока, поэтому GUI обязан передать безопасную
                обёртку (NFR-05).

        Returns:
            :class:`RenderResult` с путём, длительностью и хвостом лога.

        Raises:
            RenderCancelled: если до или во время работы вызвана `cancel()`
                (FR-51, v0.2).
            VideoTimerError: `output: не удалось создать папку <путь>` — папка
                результата не создалась (FR-41); либо `render: ffmpeg завершился
                с ошибкой`, если код возврата ненулевой, и в конце текста —
                хвост лога для диагностики, но не весь (FR-42, NFR-04).

        Пример:
            FFmpegRenderer(cfg).run(lambda done, total: print(f"{done:.0%}"))
        """
        if self._cancelled:
            raise RenderCancelled("render: остановлен до запуска")

        total = self.cfg.known_total_duration()
        tail = _new_log_tail()
        last_seconds: float | None = None

        _make_output_dir(self.cfg.output)

        command = self.build_command()[:-1] + [
            "-progress",
            "pipe:2",
            "-nostats",
            str(self.cfg.output),
        ]

        try:
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
        except OSError as error:
            raise VideoTimerError(
                f"render: не удалось запустить ffmpeg: {error.strerror or error}"
            ) from None

        process = self._process
        assert process.stderr is not None
        try:
            for line in process.stderr:
                line = line.rstrip("\n")
                if not line:
                    continue
                tail.append(line)

                seconds = _progress_seconds(line)
                if seconds is not None:
                    last_seconds = seconds
                    if on_progress is not None and total:
                        on_progress(min(1.0, seconds / total), total)
                elif line.startswith("progress=end") and on_progress is not None:
                    on_progress(1.0, total)
        except BaseException:
            # Колбэк прогресса приходит из GUI и может упасть. Без этой
            # ветки ffmpeg остался бы работать: цикл вышел бы мимо `wait()`,
            # а процесс продолжил бы писать в переполненный канал (NFR-05).
            _stop_process(process)
            raise

        returncode = process.wait()
        self._process = None

        if self._cancelled:
            raise RenderCancelled("render: остановлен")

        if returncode != 0:
            raise VideoTimerError(
                "render: ffmpeg завершился с ошибкой. "
                + _tail_for_message(tail)
            )

        return RenderResult(
            output=self.cfg.output,
            duration_seconds=_rendered_duration(last_seconds, total),
            tail_log="\n".join(tail),
        )

    # since: v0.2 (FR-51)
    def cancel(self) -> None:
        """Остановить идущий рендер.

        Спека: FR-51. Версия: v0.2 (критерий A9: отмена останавливает ffmpeg).

        Вызывается из потока GUI, поэтому делает только две вещи: ставит флаг
        отмены и завершает процесс ffmpeg. Метод безопасен, если рендер ещё
        не начался, и не бросает исключений, если процесс уже закончился.

        Поведение недописанного выходного файла (удалять или оставить)
        перенесено в v0.3 — открытый вопрос 4 в `SPEC.md`.
        """
        raise NotImplementedError


# since: v0.1 (FR-40, FR-50, FR-51)
def render(
    cfg: TimerConfig, on_progress: Callable[[float, float | None], None] | None = None
) -> RenderResult:
    """Проверить конфигурацию и выполнить рендер.

    Спека: FR-40, FR-42, FR-50. Версия: v0.1.

    Единственная точка входа для `cli` и `gui`: проверка и запуск всегда
    идут вместе, поэтому вызвать ffmpeg с непроверенной конфигурацией
    из интерфейса невозможно (FR-40).

    Args:
        cfg: конфигурация рендера из CLI или GUI.
        on_progress: колбэк прогресса, передаётся в `FFmpegRenderer.run()`.

    Returns:
        :class:`RenderResult` на успехе.

    Raises:
        VideoTimerError: из `TimerConfig.validate()` — с текстом «поле: что не
            так», ffmpeg при этом не запускался (критерий A7); либо из
            `FFmpegRenderer.run()` при ошибке ffmpeg (FR-42).
        RenderCancelled: при отмене рендера (v0.2).

    Пример:
        result = render(cfg)
        print(result.output)
    """
    cfg.validate()
    return FFmpegRenderer(cfg).run(on_progress)


# since: v0.1 (FR-41)
def _make_output_dir(output: Path) -> None:
    """Создать папку результата вместе с промежуточными каталогами.

    Спека: FR-41. Версия: v0.1.

    `TimerConfig.validate()` работает без побочных эффектов, поэтому папку
    создаёт рендер. Без этого ffmpeg падает с `No such file or directory`, а
    пользователю показывается сообщение про ffmpeg вместо его собственного
    поля `output`.

    Args:
        output: путь будущего файла, его родительская папка создаётся.

    Returns:
        Ничего.

    Raises:
        VideoTimerError: `output: не удалось создать папку <путь>: <причина>` —
            нет прав на запись или путь занят файлом (FR-41, FR-42).
    """
    parent = output.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise VideoTimerError(
            f"output: не удалось создать папку {parent}: {error.strerror or error}"
        ) from None


# since: v0.1 (NFR-05)
def _stop_process(process: subprocess.Popen) -> None:
    """Завершить процесс ffmpeg, если рендер прервался изнутри.

    Спека: NFR-05. Версия: v0.1.

    Нужен там, где `run()` выходит по исключению, а `wait()` не был вызван:
    процесс остался бы работать, продолжая писать в канал, который никто
    больше не читает. Сначала `terminate()` — ffmpeg успевает закрыть файл
    корректно; если не послушал, добиваем `kill()`.

    Args:
        process: запущенный процесс ffmpeg.

    Returns:
        Ничего. Исключения не бросаются: сбой уже происходит, и его нельзя
        заменять ошибкой завершения.
    """
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=_STOP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
    except OSError:
        pass


# since: v0.1 (NFR-04)
def _new_log_tail() -> deque[str]:
    """Создать очередь для хранения хвоста лога ffmpeg.

    Спека: NFR-04. Версия: v0.1.

    Returns:
        Пустую `deque` с максимальной длиной :data:`LOG_TAIL_LINES`.
    """
    return deque(maxlen=LOG_TAIL_LINES)


# since: v0.1 (FR-11, FR-12)
def _rendered_duration(last_seconds: float | None, total: float | None) -> float | None:
    """Определить длительность ролика по последнему отсчёту ffmpeg.

    Спека: FR-11, FR-12. Версия: v0.1.

    Args:
        last_seconds: последнее значение `out_time_us` из `-progress`, `None`
            если ffmpeg не успел ничего отдать.
        total: плановая длительность из `TimerConfig.known_total_duration()`,
            `None` если она неизвестна.

    Returns:
        Фактический хронометраж, а если его нет — плановый; `None`, если
        неизвестны оба.
    """
    return last_seconds if last_seconds is not None else total


# since: v0.1 (FR-51)
def _progress_seconds(line: str) -> float | None:
    """Достать прошедшее время рендера из строки `-progress pipe:2`.

    Спека: FR-51. Версия: v0.1.

    ffmpeg пишет `out_time_us` (микросекунды) и `out_time_ms` — историческое
    имя поля, но значение тоже в микросекундах. Берётся `out_time_us`, если
    он есть, иначе `out_time_ms`.

    Args:
        line: одна строка вывода `-progress` без перевода строки.

    Returns:
        Прошедшие секунды или ``None``, если строка не содержит времени.

    Raises:
        Не бросает исключений.
    """
    for key in ("out_time_us", "out_time_ms"):
        prefix = f"{key}="
        if line.startswith(prefix):
            try:
                return int(line[len(prefix):]) / 1_000_000
            except ValueError:
                return None
    return None


# since: v0.1 (FR-42, NFR-04)
def _tail_for_message(tail: deque[str]) -> str:
    """Собрать короткий хвост лога для сообщения об ошибке.

    Спека: FR-42, NFR-04. Версия: v0.1.

    Берутся последние :data:`_MAX_LOG_LINES` строк: причина ошибки в ffmpeg
    всегда в самом конце вывода, а до неё лежит баннер сборки — перечень
    кодеков и версий библиотек, который пользователю ничего не говорит.
    Полный хвост остаётся в `RenderResult.tail_log` для журнала GUI (FR-53).

    Args:
        tail: накопленные строки лога, не более :data:`LOG_TAIL_LINES`.

    Returns:
        Текст для конца сообщения: непустая строка либо «подробности в логе»,
            если лог был пуст.

    Raises:
        Не бросает исключений.

    Пример:
        _tail_for_message(deque(["стар", "финал"], maxlen=50))
        # "стар\\nфинал"
    """
    lines = [line for line in list(tail)[-_MAX_LOG_LINES:] if line.strip()]
    if not lines:
        return "Подробности в логе ffmpeg"
    text = "\n".join(lines)
    if len(text) > _MAX_LOG_CHARS:
        text = "…" + text[-_MAX_LOG_CHARS:]
    return text
