"""CSV export helpers for AnalysisDialog and tabs.

Provides small utilities to convert plot series or QTableWidget contents
into CSV text suitable for copying to clipboard.
"""

from __future__ import annotations

from typing import Dict, Iterable

import numpy as np


def series_to_csv(xs: np.ndarray, series: Dict[str, np.ndarray], *, cast_int: bool = False) -> str:
    """Build CSV from shared x-array and multiple named y-series.

    Parameters
    ----------
    xs: 1D numpy array for the x-axis
    series: dict of name -> 1D numpy array (same length as xs)
    cast_int: if True, y data are cast to int before export (for histogram counts)
    """
    keys = list(series.keys())
    if not keys:
        return ""
    data_cols = [series[k] for k in keys]
    if cast_int:
        data_cols = [np.asarray(col).astype(int) for col in data_cols]
    mat = np.column_stack([xs] + data_cols)
    header = ",".join(["x"] + keys)
    lines = [header]
    for row in mat:
        # keep x as-is; y as int or float repr
        lines.append(",".join(map(str, row)))
    return "\n".join(lines)


def table_to_csv(table) -> str:
    """Export entire QTableWidget (with header) to CSV text.

    Accepts a QTableWidget-like object (Qt not imported here to avoid hard dependency).
    """
    cols = table.columnCount()
    header_labels = [
        table.horizontalHeaderItem(c).text() if table.horizontalHeaderItem(c) is not None else "" for c in range(cols)
    ]
    rows = table.rowCount()
    out_lines = [",".join(header_labels)]
    for r in range(rows):
        row_vals = [table.item(r, c).text() if table.item(r, c) is not None else "" for c in range(cols)]
        out_lines.append(",".join(row_vals))
    return "\n".join(out_lines)


def selection_to_csv(table) -> str:
    """Convert the selected region of a QTableWidget to CSV text.

    If multiple non-contiguous ranges are selected, the first range is used.
    If nothing is selected, the whole table is exported.
    """
    ranges = table.selectedRanges()
    cols = table.columnCount()
    header_labels = [
        table.horizontalHeaderItem(c).text() if table.horizontalHeaderItem(c) is not None else "" for c in range(cols)
    ]

    if not ranges:
        return table_to_csv(table)

    r = ranges[0]
    sel_header = [header_labels[c] for c in range(r.leftColumn(), r.rightColumn() + 1)]
    out_lines = [",".join(sel_header)]
    for row in range(r.topRow(), r.bottomRow() + 1):
        vals = []
        for col in range(r.leftColumn(), r.rightColumn() + 1):
            item = table.item(row, col)
            vals.append(item.text() if item is not None else "")
        out_lines.append(",".join(vals))
    return "\n".join(out_lines)
