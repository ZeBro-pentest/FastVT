"""Выбор кодека вывода: по расширению файла и по явному `--encoder`.

Модуль хранит таблицу «расширение → кодек», умеет опрашивать сборку ffmpeg
и отсекать несовместимые пары. Зависимости: `config` (ради импорта
`VideoTimerError` и имён полей), стандартная библиотека. `renderer`
импортирует этот модуль, обратных импортов нет.

Ограничение намеренное (SPEC 7.4): проверка подтверждает, что кодек есть
в сборке ffmpeg, но не что есть железо. Для `h264_nvenc` на машине без
NVIDIA ошибку даст сам ffmpeg — это документируется, а не детектится.
"""

from __future__ import annotations

from pathlib import Path

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
    raise NotImplementedError


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
    raise NotImplementedError
