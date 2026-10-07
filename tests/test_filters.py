"""Тесты сборки цепочки фильтров.

Проверяется то, что уходит в `-filter_complex`: `drawtext` таймера, позиция,
экранирование текста, фаза hold и завершающий `format=yuv420p`. Критерии A1 и
A2 относятся к результату рендера, здесь проверяется только то, как он собран.

Масштабирование (`fit`, своё разрешение, критерии A3 и A4) и подложка
(`bg_style`, FR-07) помечены в спеке как v0.2 и остаются заглушками.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from video_timer.background import Background
from video_timer.config import TimerConfig, VideoTimerError
from video_timer.filters import FilterBuilder


@pytest.fixture
def countdown_cfg(tmp_output: Path) -> TimerConfig:
    """Конфигурация критерия A1: отсчёт 10 с, hold 5 с, чёрный фон."""
    return TimerConfig(
        output=tmp_output,
        mode="countdown",
        countdown_seconds=10.0,
        hold_seconds=5.0,
    )


def builder(cfg: TimerConfig) -> FilterBuilder:
    """Собрать `FilterBuilder` поверх свежего фона для конфигурации."""
    return FilterBuilder(cfg, Background(cfg))


def _ffmpeg_accepts(chain: list[str]) -> bool:
    """Попросить ffmpeg построить граф фильтров из цепочки.

    Спека: FR-01, FR-03, FR-13, инвариант SPEC 7.3. Версия: v0.1.

    Кадр не кодируется: ffmpeg только строит граф и сразу выходит, поэтому
    проверка быстрая и не зависит от кодеков, установленных в системе.

    Args:
        chain: список фильтров из `FilterBuilder.build()`.

    Returns:
        `True`, если ffmpeg принял цепочку без ошибок разбора.
    """
    import subprocess

    from video_timer import osutil

    ffmpeg = osutil.find_ffmpeg()
    if ffmpeg is None:
        return False

    result = subprocess.run(
        [
            str(ffmpeg),
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=64x64:r=1:d=1",
            "-filter_complex",
            ",".join(chain),
            "-frames:v",
            "1",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
    )
    return result.returncode == 0


def test_build_returns_list_of_filters(base_cfg: TimerConfig) -> None:
    """`build()` возвращает список строк, а не одну склеенную строку."""
    chain = builder(base_cfg).build()

    assert isinstance(chain, list)
    assert all(isinstance(item, str) for item in chain)
    assert len(chain) >= 2


def test_build_ends_with_pix_fmt_yuv420p(base_cfg: TimerConfig) -> None:
    """Последним идёт `format=yuv420p`, иначе mp4 не собирается (FR-20)."""
    assert builder(base_cfg).build()[-1] == "format=yuv420p"


def test_timer_filter_contains_drawtext(base_cfg: TimerConfig) -> None:
    """Таймер рисуется фильтром `drawtext` (FR-01)."""
    chain = builder(base_cfg).build()

    assert any(item.startswith("drawtext=") for item in chain)


def test_timer_text_uses_clock_expression(base_cfg: TimerConfig) -> None:
    """Секундомер берёт время кадра `t` (FR-01)."""
    timer = builder(base_cfg).build_timer_filters()[0]

    assert "text=" in timer
    assert "eif" in timer


def test_countdown_text_escaped_once_per_level(base_cfg: TimerConfig) -> None:
    """Двоеточие в тексте часов экранируется ровно двумя слэшами (SPEC 7.3).

    `text=` разбирается дважды — фильтром и `drawtext`, — поэтому ровно два
    обратных слэша: один слэш ffmpeg не примет, три нарисуют лишний символ.
    """
    timer = builder(base_cfg).build_timer_filters()[0]

    assert "\\\\:" in timer
    assert "\\\\\\\\:" not in timer


def test_stopwatch_position_br_is_bottom_right(base_cfg: TimerConfig) -> None:
    """Позиция `br` даёт координаты у правого нижнего угла (FR-05)."""
    base_cfg.position = "br"
    timer = builder(base_cfg).build_timer_filters()[0]

    assert "x=w-tw-" in timer
    assert "y=h-th-" in timer


def test_position_tl_is_top_left(base_cfg: TimerConfig) -> None:
    """Позиция `tl` даёт фиксированные отступы от левого верхнего угла (FR-05)."""
    base_cfg.position = "tl"
    timer = builder(base_cfg).build_timer_filters()[0]

    assert "x=40" in timer
    assert "y=40" in timer


def test_position_center_maps_to_center(base_cfg: TimerConfig) -> None:
    """Позиция `center` даёт координаты по центру кадра (FR-05)."""
    base_cfg.position = "center"
    timer = builder(base_cfg).build_timer_filters()[0]

    assert "x=(w-tw)/2" in timer
    assert "y=(h-th)/2" in timer


def test_every_position_produces_distinct_coordinates(
    base_cfg: TimerConfig,
) -> None:
    """Все пять позиций из `POSITIONS` дают разные x и y (FR-05)."""
    from video_timer.config import POSITIONS

    seen = set()
    for position in POSITIONS:
        base_cfg.position = position
        timer = builder(base_cfg).build_timer_filters()[0]
        x = [part for part in timer.split(":") if part.startswith("x=")]
        y = [part for part in timer.split(":") if part.startswith("y=")]
        seen.add((tuple(x), tuple(y)))

    assert len(seen) == len(POSITIONS)


def test_font_size_reaches_drawtext(base_cfg: TimerConfig) -> None:
    """`font-size` попадает в параметры `drawtext` (FR-06)."""
    base_cfg.font_size = 96
    timer = builder(base_cfg).build_timer_filters()[0]

    assert "fontsize=96" in timer


def test_font_color_reaches_drawtext(base_cfg: TimerConfig) -> None:
    """Цвет текста попадает в параметры `drawtext` (FR-06)."""
    base_cfg.color = "yellow"
    timer = builder(base_cfg).build_timer_filters()[0]

    assert "color=yellow" in timer


def test_font_file_reaches_drawtext(base_cfg: TimerConfig, tmp_path: Path) -> None:
    """Свой шрифт подставляется как `fontfile` (FR-06)."""
    font = tmp_path / "my.ttf"
    font.write_bytes(b"")
    base_cfg.font = font
    timer = builder(base_cfg).build_timer_filters()[0]

    assert f"fontfile={font}" in timer


def test_system_font_used_when_none(base_cfg: TimerConfig) -> None:
    """Без своего шрифта берётся системный (FR-06)."""
    from video_timer import osutil

    base_cfg.font = None
    timer = builder(base_cfg).build_timer_filters()[0]

    assert f"fontfile={osutil.default_font()}" in timer


def test_hold_filter_uses_hold_color(countdown_cfg: TimerConfig) -> None:
    """Фаза hold рисуется вторым `drawtext` с hold-цветом (FR-03)."""
    filters = builder(countdown_cfg).build_timer_filters()

    assert len(filters) == 2
    assert f"color={countdown_cfg.hold_color}" in filters[1]
    assert "text=00\\\\:00" in filters[1]


def test_hold_filter_absent_when_hold_seconds_zero(
    countdown_cfg: TimerConfig,
) -> None:
    """При `hold-seconds 0` фазовый фильтр не добавляется (FR-03)."""
    countdown_cfg.hold_seconds = 0

    assert len(builder(countdown_cfg).build_timer_filters()) == 1


def test_hold_filter_absent_for_stopwatch(base_cfg: TimerConfig) -> None:
    """У секундомера обнуления нет, поэтому фазы hold нет (FR-03)."""
    base_cfg.mode = "stopwatch"

    assert len(builder(base_cfg).build_timer_filters()) == 1


def test_hold_enabled_between_ten_and_fifteen_seconds(
    countdown_cfg: TimerConfig,
) -> None:
    """При N=10 и hold=5 красный `00:00` горит с 10-й по 15-ю секунду (A1)."""
    hold = builder(countdown_cfg).build_timer_filters()[1]

    assert "enable=" in hold
    assert "between(t\\,10\\,15)" in hold


def test_main_timer_hidden_after_countdown_zero(
    countdown_cfg: TimerConfig,
) -> None:
    """Основной таймер гаснет в момент обнуления, иначе будет двойной `00:00` (A1)."""
    main = builder(countdown_cfg).build_timer_filters()[0]

    assert "enable=" in main
    assert "lt(t\\,10)" in main


def test_text_disappears_after_hold(countdown_cfg: TimerConfig) -> None:
    """После hold ни один таймер не рисуется (FR-03, критерий A1)."""
    filters = builder(countdown_cfg).build_timer_filters()

    for item in filters:
        if "enable=" in item:
            assert "between(t\\,10\\,15)" in item or "lt(t\\,10)" in item


def test_missing_font_raises_readable_error(
    base_cfg: TimerConfig, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Нет ни своего шрифта, ни системного — понятная ошибка, а не пустой текст."""
    from video_timer import osutil

    monkeypatch.setattr(osutil, "default_font", lambda: None)
    base_cfg.font = None

    with pytest.raises(VideoTimerError, match=r"^font: "):
        builder(base_cfg).build_timer_filters()


def test_scale_filter_none_without_resolution(base_cfg: TimerConfig) -> None:
    """Без `resolution` масштабирование не добавляется (v0.1, FR-13)."""
    assert FilterBuilder(base_cfg, Background(base_cfg)).build_scale_filter() is None


def test_timer_chain_is_parsed_by_real_ffmpeg(base_cfg: TimerConfig) -> None:
    """Собранная цепочка разбирается настоящим ffmpeg без ошибок (FR-01).

    Строка проверки — не только про синтаксис: неверное число слэшей перед
    двоеточием или запятой ffmpeg пропускает молча в одних случаях и падает
    в других. Тест ловит оба.
    """
    assert _ffmpeg_accepts(builder(base_cfg).build())


def test_countdown_chain_is_parsed_by_real_ffmpeg(countdown_cfg: TimerConfig) -> None:
    """Цепочка отсчёта с фазой hold разбирается ffmpeg (A1, FR-03)."""
    assert _ffmpeg_accepts(builder(countdown_cfg).build())


def test_builder_accepts_background(base_cfg: TimerConfig) -> None:
    """`FilterBuilder` берёт тип фона из `Background` (FR-10)."""
    background = Background(base_cfg)
    filters = FilterBuilder(base_cfg, background).build()

    assert filters[-1] == "format=yuv420p"


def test_build_is_idempotent(base_cfg: TimerConfig) -> None:
    """Повторный `build()` даёт ту же цепочку — состояние не меняется (FR-40)."""
    instance = builder(base_cfg)

    assert instance.build() == instance.build()


def test_parts_are_not_duplicated(base_cfg: TimerConfig) -> None:
    """Масштаб и таймер не дублируются при сборке полной цепочки (FR-13)."""
    chain = builder(base_cfg).build()
    timers = [item for item in chain if item.startswith("drawtext=")]

    assert len(timers) == len(builder(base_cfg).build_timer_filters())
    assert chain.count("format=yuv420p") == 1


def test_scale_filter_contain_pads_black_bars(base_cfg: TimerConfig) -> None:
    """`contain` добавляет `pad` чёрными полями (FR-14, критерий A3)."""
    pytest.fail("не реализовано: A3 — fit=contain добавляет pad (v0.2)")


def test_scale_filter_cover_crops_edges(base_cfg: TimerConfig) -> None:
    """`cover` добавляет `crop` без полей (FR-14, критерий A4)."""
    pytest.fail("не реализовано: A4 — fit=cover добавляет crop (v0.2)")


def test_scale_filter_stretch_has_no_pad(base_cfg: TimerConfig) -> None:
    """`stretch` только масштабирует, без `pad` и `crop` (FR-14)."""
    pytest.fail("не реализовано: FR-14 — fit=stretch без pad и crop (v0.2)")


def test_shadow_style_adds_box_filter(base_cfg: TimerConfig) -> None:
    """Подложка `shadow` добавляет фильтр тени под текстом (FR-07)."""
    pytest.fail("не реализовано: FR-07 — box подложка для bg_style=shadow (v0.2)")