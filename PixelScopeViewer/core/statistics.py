"""histogram・profile・統計量の計算（Qt 非依存）。"""

from __future__ import annotations

import numpy as np


def determine_hist_bins(arr: np.ndarray, bin_step: float) -> np.ndarray:
    """データの範囲を bin_step 刻みで覆う histogram の bin 境界を返す。"""
    step = bin_step
    data_min = np.floor(arr.min() / step) * step
    data_max = np.ceil(arr.max() / step) * step
    return np.arange(data_min, data_max + step, step)


def determine_hist_bins_auto(arr: np.ndarray) -> np.ndarray | int:
    """dtype に応じた histogram の bin を返す。

    float は値の範囲に応じて 1 または 0.005 刻みの bin 境界、整数は (max - min + 1) 個の bin 数を返す。
    """
    if np.issubdtype(arr.dtype, np.floating):
        data_min = arr.min()
        data_max = arr.max()
        step = 1
        if data_max - data_min > 5:
            data_min = int(data_min)
            data_max = int(data_max + 0.5)
        else:
            data_min = int(data_min * 100) / 100
            data_max = int(data_max * 100 + 0.5) / 100
            step = 0.005
        bins = np.arange(data_min, data_max, step)
        return bins
    data_min = arr.min()
    data_max = arr.max()
    return max(1, int(data_max - data_min) + 1)


def crop_roi(arr: np.ndarray, rect: tuple[int, int, int, int] | None) -> np.ndarray:
    """ROI (x, y, w, h) の範囲を切り出す。ROI がない場合は左上 1 pixel を返す。"""
    if rect is None:
        return arr[0:1, 0:1]
    x, y, w, h = (int(v) for v in rect)
    return arr[y : y + h, x : x + w]


def merge_hist_series(
    series: dict[str, tuple[np.ndarray, np.ndarray]], mode: str
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """複数の histogram / ECDF の系列を共通の x 軸に揃える。

    x 軸は全系列の x の和集合（前後 1 step を含む）。ECDF は前後の累積確率で補間し、Histogram は値のない x を 0 にする。
    """
    all_xs = []
    for xs, _ in series.values():
        xs = np.asarray(xs)
        dx = xs[1] - xs[0] if len(xs) > 1 else 1.0
        all_xs.append(np.concatenate([xs, xs - dx, xs + dx]))
    x_common = np.unique(np.concatenate(all_xs)) if all_xs else np.array([])

    merged = {}
    for label, (xs, ys) in series.items():
        if mode == "ECDF":
            if len(xs) > 0:
                ys_new = np.interp(x_common, xs, ys, left=0.0, right=1.0)
            else:
                ys_new = np.zeros_like(x_common, dtype=float)
        else:
            ys_new = np.zeros_like(x_common, dtype=ys.dtype)
            indices = np.searchsorted(x_common, xs)
            valid = (indices >= 0) & (indices < len(x_common))
            ys_new[indices[valid]] = ys[valid]
        merged[label] = (x_common, ys_new)
    return merged


def _iter_channels(arr: np.ndarray) -> list[tuple[int, str, np.ndarray]]:
    """(channel index, label, 2 次元配列) のリストを返す。label は多 channel なら 'C{index}'、1ch なら 'I'。"""
    if arr.ndim == 3 and arr.shape[2] > 1:
        return [(c, f"C{c}", arr[:, :, c]) for c in range(arr.shape[2])]
    return [(0, "I", arr if arr.ndim == 2 else arr[:, :, 0])]


def histogram_series(arr: np.ndarray, *, bins: np.ndarray | None = None) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """channel ごとの histogram を計算する。

    Returns:
        label から (x, 度数) への dict。label は多 channel なら 'C{index}'、1ch なら 'I'。
    """
    if bins is None:
        # 複数画像解析用
        bins = determine_hist_bins_auto(arr)

    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for _, label, channel in _iter_channels(arr):
        data = channel.ravel()
        if np.issubdtype(data.dtype, np.integer):
            # 整数は全 channel 共通の範囲で 1 刻みの bin にし、x は bin の左端
            hist, edges = np.histogram(data, bins=bins, range=(arr.min(), arr.max() + 1))
            xs = edges[:-1]
        else:
            hist, edges = np.histogram(data, bins=bins)
            xs = (edges[:-1] + edges[1:]) / 2.0
        out[label] = (xs, hist)
    return out


def ecdf_series(arr: np.ndarray, *, max_points: int = 2000) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """channel ごとの ECDF を、最大 max_points 点に間引いて計算する。"""
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for _, label, channel in _iter_channels(arr):
        data = channel.ravel()
        if len(data) > max_points:
            # np.random.choice よりスライス（ストライド抽出）の方が高速
            data = data[:: len(data) // max_points][:max_points]
        xs = np.sort(data)
        # 0.0 ~ 1.0 の累積確率
        out[label] = (xs, np.linspace(1.0 / len(xs), 1.0, len(xs)))
    return out


def compute_profile_1d(channel_data: np.ndarray, orientation: str, method: str = "mean") -> np.ndarray:
    """1ch の 2 次元配列から profile を計算する。

    Args:
        channel_data: 1ch の 2 次元配列。
        orientation: 'h'（水平）または 'v'（垂直）。
        method: 'mean', 'std', 'min', 'max', 'p2p', 'median' のいずれか。
    """
    axis = 0 if orientation == "h" else 1

    if method == "mean":
        return np.mean(channel_data, axis=axis)
    elif method == "std":
        return np.std(channel_data, axis=axis)
    elif method == "max":
        return np.max(channel_data, axis=axis)
    elif method == "min":
        return np.min(channel_data, axis=axis)
    elif method == "p2p":
        return np.ptp(channel_data, axis=axis)
    elif method == "median":
        return np.median(channel_data, axis=axis)


def profile_series(arr: np.ndarray, *, orientation: str = "h", method: str = "mean") -> dict[str, np.ndarray]:
    """channel ごとの profile を計算する。

    Returns:
        label から profile 配列への dict。label は多 channel なら 'C{index}'、1ch なら 'I'。
    """
    return {label: compute_profile_1d(channel, orientation, method) for _, label, channel in _iter_channels(arr)}


def get_profile_offset(image_rect, orientation: str) -> int:
    """absolute 表示で x 軸に加える offset（ROI の開始座標）を返す。"""
    if image_rect is None:
        return 0
    if orientation == "h":
        return int(image_rect.x())
    if orientation == "v":
        return int(image_rect.y())
    return int(min(image_rect.x(), image_rect.y()))


# --- 統計量 ---


def calc_stats(data: np.ndarray) -> tuple[float, float, float, float, float, float]:
    """mean, std, median, min, max, fano factor を返す。データが空の場合はすべて NaN。"""
    if data.size == 0:
        mean = std = median = min = max = fano = np.nan
    else:
        mean = np.mean(data)
        std = np.std(data)
        median = np.median(data)
        min = np.min(data)
        max = np.max(data)
        fano = std**2 / mean
    return mean, std, median, min, max, fano


def stats_row(index: int, label: str, data: np.ndarray, is_int: bool) -> dict:
    """統計量 table の 1 行（ch, curve_label, mean, std, median, min, max, fano, is_int）を返す。"""
    mean_v, std_v, median_v, min_v, max_v, fano_v = calc_stats(data)
    return {
        "ch": str(index),
        "curve_label": label,  # 色の対応付けに使う label
        "mean": mean_v,
        "std": std_v,
        "median": median_v,
        "min": min_v,
        "max": max_v,
        "fano": fano_v,
        "is_int": is_int,
    }


def _visible_channels(arr: np.ndarray, channel_checks: list[bool] | None):
    """表示 ON の channel だけを返す。1ch の場合は channel_checks に関係なく返す。"""
    channels = _iter_channels(arr)
    if len(channels) == 1 and channels[0][1] == "I":
        return channels
    checks = channel_checks or [True] * len(channels)
    return [ch for ch in channels if not (ch[0] < len(checks) and not checks[ch[0]])]


def histogram_stats(arr: np.ndarray, channel_checks: list[bool] | None = None):
    """histogram 表示用に channel ごとの統計量を計算する。

    Args:
        arr: 画像配列。
        channel_checks: channel ごとの表示 ON/OFF。False の channel は除外する。

    Returns:
        ch, curve_label, mean, std, median, min, max, fano, is_int を持つ dict のリスト。
    """
    return [
        stats_row(c, label, channel.ravel(), bool(np.issubdtype(channel.dtype, np.integer)))
        for c, label, channel in _visible_channels(arr, channel_checks)
    ]


def profile_stats(
    arr: np.ndarray, *, orientation: str = "h", method: str = "mean", channel_checks: list[bool] | None = None
):
    """profile 表示用に、channel ごとの profile の統計量を計算する。

    Returns:
        histogram_stats と同じ形式の dict のリスト。
    """
    rows = []
    for c, label, channel in _visible_channels(arr, channel_checks):
        prof = compute_profile_1d(channel, orientation, method)
        rows.append(stats_row(c, label, prof, bool(np.issubdtype(channel.dtype, np.integer))))
    return rows
