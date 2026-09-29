"""Тесты сборки цепочки фильтров.

Проверяется то, что уходит в `-filter_complex`: подложка, позиция, экранирование
в `drawtext`, режим `fit`. Критерии A1, A3 и A4 относятся к результату
рендера, здесь проверяется только то, как он собран.
"""

from __future__ import annotations

import pytest

from video_timer.background import Background
from video_timer.config import TimerConfig
from video_timer.filters import FilterBuilder


def test_build_returns_list_of_filters(base_cfg: TimerConfig) -> None:
    """`build()` возвращает список строк, а не одну склеенную строку."""
    pytest.fail("не реализовано: FR-01 — build() возвращает список фильтров")


def test_build_ends_with_pix_fmt_yuv420p(base_cfg: TimerConfig) -> None:
    """Последним идёт `format=yuv420p`, иначе mp4 не собирается (FR-20)."""
    pytest.fail("не реализовано: FR-20 — format=yuv420p в конце цепочки")


def test_timer_filter_contains_drawtext(base_cfg: TimerConfig) -> None:
    """Таймер рисуется фильтром `drawtext` (FR-01)."""
    pytest.fail("не реализовано: FR-01 — в цепочке есть drawtext")


def test_countdown_text_not_escaped_twice(base_cfg: TimerConfig) -> None:
    """Двоеточие в тексте часов экранируется ровно один раз (SPEC 7.3)."""
    pytest.fail("не реализовано: SPEC 7.3 — одинарное экранирование в drawtext")


def test_stopwatch_position_br_is_bottom_right(base_cfg: TimerConfig) -> None:
    """Позиция `br` даёт координаты у правого нижнего угла (FR-05)."""
    pytest.fail("не реализовано: FR-05 — координаты для position=br")


def test_position_center_maps_to_center(base_cfg: TimerConfig) -> None:
    """Позиция `center` даёт координаты по центру кадра (FR-05)."""
    pytest.fail("не реализовано: FR-05 — координаты для position=center")


def test_font_size_reaches_drawtext(base_cfg: TimerConfig) -> None:
    """`font-size` попадает в параметры `drawtext` (FR-06)."""
    pytest.fail("не реализовано: FR-06 — fontsize в drawtext")


def test_font_color_reaches_drawtext(base_cfg: TimerConfig) -> None:
    """Цвет текста попадает в параметры `drawtext` (FR-06)."""
    pytest.fail("не реализовано: FR-06 — color в drawtext")


def test_hold_filter_uses_hold_color(base_cfg: TimerConfig) -> None:
    """Фаза hold рисуется вторым `drawtext` с `hold-color` (FR-03)."""
    pytest.fail("не реализовано: FR-03 — отдельный drawtext с hold-color")


def test_hold_filter_absent_when_hold_seconds_zero(base_cfg: TimerConfig) -> None:
    """При `hold-seconds 0` фазовый фильтр не добавляется (FR-03)."""
    pytest.fail("не реализовано: FR-03 — без hold-фильтра при hold-seconds 0")


def test_hold_enabled_between_ten_and_fifteen_seconds(base_cfg: TimerConfig) -> None:
    """При N=10 и hold=5 красный `00:00` горит с 10-й по 15-ю секунду (A1)."""
    pytest.fail("не реализовано: A1 — окно показа hold 10…15 секунд")


def test_text_disappears_after_hold(base_cfg: TimerConfig) -> None:
    """После hold ни один таймер не рисуется (FR-03, критерий A1)."""
    pytest.fail("не реализовано: A1 — текст исчезает после hold")


def test_shadow_style_adds_box_filter(base_cfg: TimerConfig) -> None:
    """Подложка `shadow` добавляет фильтр тени под текстом (FR-07)."""
    pytest.fail("не реализовано: FR-07 — box подложка для bg_style=shadow")


def test_missing_font_raises_readable_error(base_cfg: TimerConfig) -> None:
    """Нет ни своего шрифта, ни системного — понятная ошибка, а не пустой текст."""
    pytest.fail("не реализовано: FR-06 — ошибка при отсутствии шрифта")


def test_scale_filter_none_without_resolution(base_cfg: TimerConfig) -> None:
    """Без `resolution` масштабирование не добавляется (v0.1, FR-13)."""
    pytest.fail("не реализовано: FR-13 — build_scale_filter() == None без resolution")


def test_scale_filter_contain_pads_black_bars(base_cfg: TimerConfig) -> None:
    """`contain` добавляет `pad` чёрными полями (FR-14, критерий A3)."""
    pytest.fail("не реализовано: A3 — fit=contain добавляет pad")


def test_scale_filter_cover_crops_edges(base_cfg: TimerConfig) -> None:
    """`cover` добавляет `crop` без полей (FR-14, критерий A4)."""
    pytest.fail("не реализовано: A4 — fit=cover добавляет crop")


def test_scale_filter_stretch_has_no_pad(base_cfg: TimerConfig) -> None:
    """`stretch` только масштабирует, без `pad` и `crop` (FR-14)."""
    pytest.fail("не реализовано: FR-14 — fit=stretch без pad и crop")


def test_builder_accepts_background(base_cfg: TimerConfig) -> None:
    """`FilterBuilder` берёт тип фона из `Background` (FR-10)."""
    pytest.fail("не реализовано: FR-10 — FilterBuilder использует Background")


def test_build_is_idempotent(base_cfg: TimerConfig) -> None:
    """Повторный `build()` даёт ту же цепочку — состояние не меняется (FR-40)."""
    pytest.fail("не реализовано: FR-40 — FilterBuilder.build() идемпотентен")


def test_parts_are_not_duplicated(base_cfg: TimerConfig) -> None:
    """Масштаб и таймер не дублируются при сборке полной цепочки (FR-13)."""
    pytest.fail("не реализовано: FR-13 — нет повторов фильтров в build()")
