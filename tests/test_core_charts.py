"""Charts without Qt (khervesheet.core.charts) and reading ranges."""

import math

import pytest

from khervesheet.core.charts import CHART_TYPES, render_svg, series_xy
from khervesheet.core.engine import Workbook


@pytest.fixture
def wb():
    wb = Workbook()
    sheet = wb.add_sheet()
    rows = [("Month", "Sales", "Cost"), ("Jan", 10, 4), ("Feb", 14, 6),
            ("Mar", "", 5), ("Apr", 20, 8)]
    for r, row in enumerate(rows):
        for c, v in enumerate(row):
            if v != "":
                sheet.set_cell(r, c, str(v))
    sheet.set_cell(5, 1, "=SUM(B2:B5)")
    wb.add_sheet("My data").set_cell(0, 0, "7")
    return wb


def test_range_values(wb):
    assert wb.range_values("B2:B5") == [10.0, 14.0, None, 20.0]
    assert wb.range_values("B6") == [44.0]
    assert wb.range_values("'My data'!A1") == [7.0]
    assert wb.range_values("A1:B2") == ["Month", "Sales", "Jan", 10.0]
    # A whole column stops at the last filled row.
    assert wb.range_values("C:C") == ["Cost", 4.0, 6.0, 5.0, 8.0, None]
    with pytest.raises(ValueError):
        wb.range_values("Nope!A1")
    with pytest.raises(ValueError):
        wb.range_values("A1:")


def test_series_xy_numeric_text_and_time():
    x, y, labels = series_xy([1, 2, 3], [5, None, 7])
    assert list(x) == [1, 3] and list(y) == [5, 7] and labels is None
    x, y, labels = series_xy(["a", "b", "c"], [1, 2, "x"])
    assert list(x) == [0, 1] and labels == ["a", "b"]
    x, y, labels = series_xy(["8:00", "9:30", "23:00", "1:00"], [1, 2, 3, 4])
    assert labels == "TIME" and math.isclose(x[1], 9.5) and x[3] == 25
    x, y, labels = series_xy(None, [3, 4])
    assert list(x) == [0, 1]


@pytest.mark.parametrize("kind", CHART_TYPES)
def test_every_type_renders(wb, kind):
    svg = render_svg({"type": kind, "x": "A2:A5", "title": "T",
                      "series": [{"ref": "B2:B5", "name": "Sales"},
                                 {"ref": "C2:C5", "name": "Cost"}]},
                     wb.range_values)
    assert svg.lstrip().startswith("<?xml") and "<svg" in svg
    assert "No numbers" not in svg


def test_text_stays_text_and_messages(wb):
    svg = render_svg({"type": "Line", "title": "Quarterly sales",
                      "series": [{"ref": "B2:B5"}]}, wb.range_values)
    assert "Quarterly sales" in svg
    assert "Choose the data" in render_svg({"series": []}, wb.range_values)
    assert "No numbers" in render_svg(
        {"series": [{"ref": "A2:A5"}]}, wb.range_values)


def test_size_follows_spec(wb):
    svg = render_svg({"series": [{"ref": "B2:B5"}], "width": 600,
                      "height": 240}, wb.range_values)
    assert 'width="450pt"' in svg and 'height="180pt"' in svg
