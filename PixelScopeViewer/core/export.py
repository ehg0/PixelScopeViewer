"""解析データを clipboard 用の CSV 文字列にする（Qt 非依存）。"""

from __future__ import annotations

import numpy as np

from PixelScopeViewer.core.statistics import calc_stats, compute_profile_1d


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
    lines = [",".join(keys)]
    for row in mat:
        lines.append(",".join(row))
    return "\n".join(lines)


def histogram_csv(hist_data: dict[str, tuple[np.ndarray, np.ndarray]], mode: str) -> str:
    """histogram（bin の範囲と度数）または ECDF（値と累積確率）の CSV を作成する。

    Args:
        hist_data: label から (x, y) への dict。先頭の系列の x を共通の x 軸として使う。
        mode: "Histogram" または "ECDF"。
    """
    keys = list(hist_data.keys())
    xs = np.array(hist_data[keys[0]][0]).flatten()

    if mode == "Histogram":
        # bin 幅から各 bin の開始・終了位置を求める
        bin_width = np.diff(xs)[0] if len(xs) > 1 else 1.0
        csv_data = {"bin_start": xs - bin_width / 2, "bin_end": xs + bin_width / 2, "bin_center": xs}
        cast_int_keys = keys  # 度数は int で出力する
    else:
        csv_data = {"value": xs}
        cast_int_keys = None

    for k in keys:
        csv_data[k] = np.array(hist_data[k][1]).flatten()
    return series_to_csv(csv_data, cast_int_keys=cast_int_keys)


def profile_csv(profile_data: dict[str, tuple[np.ndarray, np.ndarray]], orientation: str) -> str:
    """profile の CSV を作成する。先頭の系列の x を共通の x 軸として使う。"""
    keys = list(profile_data.keys())
    csv_data = {"x address" if orientation == "h" else "y address": profile_data[keys[0]][0]}
    for k in keys:
        csv_data[k] = profile_data[k][1]
    return series_to_csv(csv_data)


def metadata_csv(rows: list[tuple[str, str]]) -> str:
    """metadata の (key, value) を CSV にする。"""
    return "\n".join(["Key,Value", *(f"{key},{value}" for key, value in rows)])


def roi_stats_csv(
    images: list[tuple[str, np.ndarray]],
    rect: tuple[int, int, int, int],
    profile: tuple[str, str] | None = None,
) -> str:
    """画像ごと・channel ごとに、ROI の統計量の CSV を作成する。

    Args:
        images: (path, 配列) のリスト。ROI が画像の範囲外にある画像は飛ばす。
        rect: 画像座標の ROI (x, y, w, h)。
        profile: (orientation, method)。指定した場合は ROI の profile の統計量にする。
    """
    x, y, w, h = rect
    profile_cols = "orientation,method," if profile else ""
    text = f"path,ch,x_sta,y_sta,width,hight,{profile_cols}mean,std,median,min,max,fano\n"

    for path, arr in images:
        height, width = arr.shape[:2]
        if x > width or (x + w) > width or y > height or (y + h) > height:
            continue
        if arr.ndim == 2:
            arr = arr[:, :, np.newaxis]

        for ch in range(arr.shape[2]):
            data = arr[y : y + h, x : x + w, ch]
            prefix = f"{path},{ch},{x},{y},{w},{h}"
            if profile:
                data = compute_profile_1d(data, *profile)
                prefix += f",{profile[0]},{profile[1]}"
            mean, std, median, min_, max_, fano = calc_stats(data)
            text += f"{prefix},{mean},{std},{median},{min_},{max_},{fano}\n"
    return text
