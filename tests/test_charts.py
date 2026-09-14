#!/usr/bin/env python
"""
Tests for chart rendering (no database required).
"""

import pytest

from oraviz_mcp.charts import CHART_TYPES, ChartError, _to_float, render_chart

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

COLUMNS = ["REGION", "ONLINE", "RETAIL"]
ROWS = [["North", 120, 80], ["South", 200, 150], ["East", 90, 60], ["West", 160, 110]]


def _png(*args, **kwargs) -> bytes:
    data = render_chart(*args, **kwargs)
    assert isinstance(data, bytes)
    assert data.startswith(PNG_MAGIC)
    return data


class TestRenderChart:
    @pytest.mark.parametrize("chart_type", CHART_TYPES)
    def test_all_types_render_png(self, chart_type):
        _png(COLUMNS, ROWS, chart_type)

    def test_titles_and_labels(self):
        _png(COLUMNS, ROWS, "bar", title="Sales", x_label="Region", y_label="Revenue")

    def test_single_series(self):
        _png(["MONTH", "REVENUE"], [["Jan", 1], ["Feb", 2]], "line")

    def test_many_series_are_capped_not_fatal(self):
        columns = ["LABEL"] + [f"S{i}" for i in range(10)]
        rows = [["row", *range(10)], ["row2", *range(10, 20)]]
        _png(columns, rows, "line")

    def test_many_categories_thins_ticks(self):
        rows = [[f"c{i}", i] for i in range(50)]
        _png(["CATEGORY", "VALUE"], rows, "bar")

    def test_none_values_do_not_break_rendering(self):
        rows = [["a", None], ["b", 2], ["c", None]]
        _png(["L", "V"], rows, "line")
        _png(["L", "V"], rows, "bar")

    def test_pie_groups_small_slices(self):
        rows = [[f"c{i}", i + 1] for i in range(20)]
        _png(["CATEGORY", "VALUE"], rows, "pie")

    def test_scatter_filters_non_numeric_pairs(self):
        rows = [[1, None], [2, 3], [None, 4]]
        _png(["X", "Y"], rows, "scatter")

    def test_histogram_single_numeric(self):
        _png(["AMOUNT"], [[1], [2], [2], [3]], "histogram")

    def test_chart_type_is_case_insensitive(self):
        _png(COLUMNS, ROWS, "BAR")


class TestRenderChartErrors:
    def test_unknown_type(self):
        with pytest.raises(ChartError, match="Unsupported chart_type"):
            render_chart(COLUMNS, ROWS, "sunburst")

    def test_empty_type(self):
        with pytest.raises(ChartError):
            render_chart(COLUMNS, ROWS, "")

    def test_no_columns(self):
        with pytest.raises(ChartError, match="no columns"):
            render_chart([], ROWS, "bar")

    def test_no_rows(self):
        with pytest.raises(ChartError, match="no rows"):
            render_chart(COLUMNS, [], "bar")

    def test_bar_needs_numeric_column(self):
        with pytest.raises(ChartError, match="numeric column"):
            render_chart(["A", "B"], [["x", "y"]], "bar")

    def test_line_needs_numeric_column(self):
        with pytest.raises(ChartError, match="numeric column"):
            render_chart(["A", "B"], [["x", "y"]], "line")

    def test_area_needs_numeric_column(self):
        with pytest.raises(ChartError, match="numeric column"):
            render_chart(["A", "B"], [["x", "y"]], "area")

    def test_scatter_needs_two_numeric_columns(self):
        with pytest.raises(ChartError, match="two numeric"):
            render_chart(["A", "B"], [["x", 1]], "scatter")

    def test_scatter_needs_a_complete_pair(self):
        with pytest.raises(ChartError, match="both columns"):
            render_chart(["X", "Y"], [[1, None], [None, 2]], "scatter")

    def test_pie_needs_numeric_column(self):
        with pytest.raises(ChartError, match="numeric column"):
            render_chart(["A", "B"], [["x", "y"]], "pie")

    def test_pie_rejects_negative_values(self):
        with pytest.raises(ChartError, match="non-negative"):
            render_chart(["A", "B"], [["x", -1]], "pie")

    def test_pie_rejects_all_zero(self):
        with pytest.raises(ChartError, match="positive"):
            render_chart(["A", "B"], [["x", 0]], "pie")

    def test_histogram_needs_numeric_column(self):
        with pytest.raises(ChartError, match="numeric column"):
            render_chart(["A"], [["x"]], "histogram")


class TestToFloat:
    def test_coercions(self):
        assert _to_float(3) == 3.0
        assert _to_float(3.5) == 3.5
        assert _to_float(" 4.25 ") == 4.25
        assert _to_float(True) is None
        assert _to_float(None) is None
        assert _to_float("abc") is None
        assert _to_float(float("inf")) is None
        assert _to_float(float("nan")) is None

    def test_decimal_like_values(self):
        import decimal

        assert _to_float(decimal.Decimal("1.25")) == 1.25
