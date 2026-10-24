"""CSV export helpers for AnalysisDialog and tabs.

Provides small utilities to convert plot series or QTableWidget contents
into CSV text suitable for copying to clipboard.
"""

from __future__ import annotations

import numpy as np


def series_to_csv(data_dict: dict[str, np.ndarray], *, cast_int_keys: list[str] | None = None) -> str:
    """複数の系列から、指定したフォーマットでCSV文字列を構築する。

    Parameters
    ----------
    data_dict: 列名 -> 1D numpy array の辞書
    cast_int_keys: 整数（int）にキャストしたい列名のリスト（ヒストグラムの度数など）
    """
    keys = list(data_dict.keys())
    if not keys:
        return ""

    if cast_int_keys is None:
        cast_int_keys = []

    formatted_cols = []
    for k in keys:
        # flatten() を入れ、万が一2次元(N, 1)が混ざっていても確実に1次元にする
        col = np.asarray(data_dict[k]).flatten()

        if k in cast_int_keys:
            # 指定された列（度数など）は int にキャストして文字列化
            cols_str = col.astype(int).astype(str)
        elif k in ["bin_start", "bin_end", "bin_center"]:
            # ビン関連の列は、小数点3桁固定の文字列にする
            cols_str = np.char.mod("%.3f", col)
        else:
            # その他（実数のプロファイルデータなど）はそのまま文字列化
            cols_str = col.astype(str)

        formatted_cols.append(cols_str)

    # 1次元配列同士を横方向に結合して、1行ずつのcsv文字列にする
    mat = np.column_stack(formatted_cols)
    header = ",".join(keys)

    lines = [header]
    for row in mat:
        lines.append(",".join(row))

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
