"""Выбор кодека вывода: по расширению файла и по явному `--encoder`.

Модуль хранит таблицу «расширение → кодек», умеет опрашивать сборку ffmpeg
и отсекать несовместимые пары. Зависимости: `config` (ради импорта
`VideoTimerError`), `osutil` (поиск ffmpeg), стандартная библиотека.
`renderer` импортирует этот модуль, обратных импортов нет.

Ограничение намеренное (SPEC 7.4): проверка подтверждает, что кодек есть
в сборке ffmpeg, но не что есть железо. Для `h264_nvenc` на машине без
NVIDIA ошибку даст сам ffmpeg — это документируется, а не детектится.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from video_timer import osutil
from video_timer.config import VideoTimerError

# since: v0.1 (FR-20), полный набор — v0.2 (FR-20, FR-21)
OUTPUT_CODECS: dict[str, dict[str, str]] = {
    ".mp4": {"video": "libx264", "audio": "aac"},
    ".mov": {"video": "libx264", "audio": "aac"},
    ".mkv": {"video": "libx264", "audio": "aac"},
    ".webm": {"video": "libvpx-vp9", "audio": "libopus"},
}
"""Кодек видео и аудио для каждого расширения вывода (FR-20).

Ключ — расширение с точкой, значение — словарь с ключами ``video`` и
``audio``. Таблица читается и `TimerConfig.resolved_encoder()`, и
`FFmpegRenderer.build_command()`.

В v0.1 допустимо только ``.mp4`` с ``libx264``; остальные строки вступают
в силу в v0.2 вместе с выбором кодека (FR-21). Кодек ``libvpx-vp9``
используется намеренно: ``libx264`` в ``.webm`` несовместим (критерий A6).
"""


# since: v0.2 (FR-21)
_VIDEO_CODECS_BY_CONTAINER: dict[str, tuple[frozenset[str], tuple[str, ...]]] = {
    ".mp4": (
        frozenset(
            {
                "libx264",
                "libopenh264",
                "libx265",
                "mpeg4",
                "libaom-av1",
                "libsvtav1",
                "librav1e",
                "av1",
            }
        ),
        ("h264_", "hevc_", "av1_"),
    ),
    ".mov": (
        frozenset(
            {
                "libx264",
                "libopenh264",
                "libx265",
                "mpeg4",
                "prores",
                "prores_ks",
                "prores_aw",
                "libaom-av1",
                "libsvtav1",
            }
        ),
        ("h264_", "hevc_", "av1_", "prores"),
    ),
    ".mkv": (
        frozenset(
            {
                "libx264",
                "libopenh264",
                "libx265",
                "mpeg4",
                "libvpx",
                "libvpx-vp9",
                "vp8",
                "vp9",
                "libaom-av1",
                "libsvtav1",
                "librav1e",
                "av1",
            }
        ),
        ("h264_", "hevc_", "av1_", "vp9_"),
    ),
    ".webm": (
        frozenset(
            {
                "libvpx",
                "libvpx-vp9",
                "vp8",
                "vp9",
                "libaom-av1",
                "libsvtav1",
                "librav1e",
                "av1",
            }
        ),
        ("vp9_",),
    ),
}
"""Совместимость видеокодеков с контейнером (FR-21).

Ключ — расширение вывода, значение — пара «точные имена, префиксы для
аппаратных вариантов». WebM принимает только VP8/VP9/AV1, поэтому `libx264`
там отвергается (критерий A6). Остальные контейнеры допускают H.264/H.265,
в том числе аппаратные виды вроде `h264_nvenc` — их ловят префиксы.
"""

# since: v0.2 (FR-22)
_ENCODERS_CACHE: set[str] | None = None
"""Кэш списка кодеков сборки ffmpeg: `ffmpeg -encoders` выполняется один раз."""


# since: v0.2 (FR-21)
def _is_compatible(output: Path, encoder: str) -> bool:
    """Проверить, что кодек совместим с контейнером выходного файла (FR-21).

    Args:
        output: путь итогового файла; его расширение — ключ таблицы
            :data:`_VIDEO_CODECS_BY_CONTAINER`.
        encoder: имя кодека видео.

    Returns:
        ``True``, если для контейнера кодек разрешён; ``False`` — если
        расширения нет в таблице или пара несовместима.
    """
    rule = _VIDEO_CODECS_BY_CONTAINER.get(output.suffix.lower())
    if rule is None:
        return False
    exact, prefixes = rule
    return encoder in exact or encoder.startswith(prefixes)


# since: v0.2 (FR-22)
def available_encoders() -> set[str]:
    """Получить список кодеков, доступных в текущей сборке ffmpeg.

    Спека: FR-22. Версия: v0.2.

    Разбирает вывод `ffmpeg -hide_banner -encoders`, оставляя только имена
    кодеков видео. Результат запоминается: повторный вызов в том же
    процессе повторно ffmpeg не запускает.

    Returns:
        Множество имён кодеков, например ``{"libx264", "libvpx-vp9", ...}``.

    Raises:
        VideoTimerError: `ffmpeg: не найден в системе` — если исполняемый
            файл не найден ни рядом с приложением, ни в `PATH`; сообщение
            с инструкцией по установке (FR-55).
    """
    global _ENCODERS_CACHE
    if _ENCODERS_CACHE is not None:
        return set(_ENCODERS_CACHE)

    ffmpeg = osutil.find_ffmpeg()
    if ffmpeg is None:
        raise VideoTimerError(
            "ffmpeg: не найден в системе. Установите ffmpeg "
            "и перезапустите программу"
        )

    finished = subprocess.run(
        [str(ffmpeg), "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if finished.returncode != 0:
        raise VideoTimerError(
            "ffmpeg: не удалось получить список кодеков этой сборки"
        )

    _ENCODERS_CACHE = _parse_encoders(finished.stdout)
    return set(_ENCODERS_CACHE)


# since: v0.2 (FR-22)
def _parse_encoders(text: str) -> set[str]:
    """Выбрать имена видео-кодеков из вывода `ffmpeg -encoders` (FR-22).

    В выводе есть шапка со строками-заголовками (`V..... = Video`) и
    разделитель. Кодеком считается строка, где первый столбец — это флаги:
    шесть символов, начинающиеся с `V` (видео), а второй столбец — имя.

    Args:
        text: весь `stdout` команды `ffmpeg -encoders`.

    Returns:
        Множество имён видео-кодеков.
    """
    names: set[str] = set()
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        flags = parts[0]
        if len(flags) != 6 or flags[0] != "V" or parts[1].startswith("="):
            continue
        names.add(parts[1])
    return names


# since: v0.2 (FR-21, FR-22)
def pick_encoder(output: Path, requested: str | None) -> str:
    """Выбрать кодек видео для выходного файла.

    Спека: FR-20, FR-21, FR-22. Версия: v0.2.

    Порядок:
        1. если `requested` задан — он выигрывает у всего, но проверяется на
           совместимость с расширением `output` и наличие в сборке ffmpeg
        2. иначе берётся кодек из :data:`OUTPUT_CODECS` по расширению

    Args:
        output: путь итогового файла; расширение должно быть из
            `OUTPUT_CODECS`.
        requested: кодек из `--encoder` или ``None`` для автоматического
            выбора.

    Returns:
        Имя кодека видео для ffmpeg.

    Raises:
        VideoTimerError: `output: расширение не поддерживается` — если
            расширения нет в :data:`OUTPUT_CODECS` (FR-20);
            `encoder: кодек несовместим с расширением вывода` — если пара
            кодек/контейнер несовместима, например `libx264` для `.webm`
            (FR-21, критерий A6);
            `encoder: кодек не найден в сборке ffmpeg` — если кодека нет в
            выводе `ffmpeg -encoders` (FR-22).

    Пример:
        pick_encoder(Path("a.webm"), None)
        # "libvpx-vp9"
    """
    suffix = output.suffix.lower()
    if suffix not in OUTPUT_CODECS:
        raise VideoTimerError(
            "output: расширение не поддерживается, допустимы: "
            + ", ".join(OUTPUT_CODECS)
        )

    if requested is None:
        return OUTPUT_CODECS[suffix]["video"]

    if not _is_compatible(output, requested):
        raise VideoTimerError(
            f"encoder: кодек {requested} несовместим с контейнером {suffix}"
        )

    if requested not in available_encoders():
        raise VideoTimerError(
            f"encoder: кодек {requested} не найден в сборке ffmpeg"
        )

    return requested
