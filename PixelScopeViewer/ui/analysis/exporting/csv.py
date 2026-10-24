"""plot の系列や table の内容を clipboard 用の CSV 文字列に変換する。"""

from __future__ import annotations

import numpy as np


def series_to_csv(data_dict: dict[str, np.ndarray], *, cast_int_keys: list[str] | None = None) -> str:
    """複数の系列を列とする CSV 文字列を作成する。

    Args:
        data_dict: 列名から 1 次元配列への dict。
        cast_int_keys: int に変換して出力する列名（histogram の度数など）。
    """
    keys = list(data_dict.keys())
    if not keys:
        return ""

    if cast_int_keys is None:
        cast_int_keys = []

    formatted_cols = []
    for k in keys:
        # (N, 1) などが混ざっても 1 次元にする
        col = np.asarray(data_dict[k]).flatten()

        if k in cast_int_keys:
            cols_str = col.astype(int).astype(str)
        elif k in ["bin_start", "bin_end", "bin_center"]:
            # bin の値は小数点以下 3 桁に揃える
            cols_str = np.char.mod("%.3f", col)
        else:
            cols_str = col.astype(str)

        formatted_cols.append(cols_str)

    mat = np.column_stack(formatted_cols)
    header = ",".join(keys)

    lines = [header]
    for row in mat:
        lines.append(",".join(row))

    return "\n".join(lines)


def table_to_csv(table) -> str:
    """QTableWidget 全体を header 付きの CSV 文字列に変換する。"""
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
    """QTableWidget の選択範囲を CSV 文字列に変換する。

    複数範囲の選択時は最初の範囲のみ、未選択時は table 全体を変換する。
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
