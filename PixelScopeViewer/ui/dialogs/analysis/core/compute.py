"""Computation helpers for AnalysisDialog.

This module centralizes histogram/profile computations and related utilities
without depending on Qt. It is safe to import in non-Qt contexts.
"""

from __future__ import annotations

import numpy as np


def determine_hist_bins(arr: np.ndarray, bin_step: float) -> np.ndarray:
    step = bin_step
    data_min = np.floor(arr.min() / step) * step
    data_max = np.ceil(arr.max() / step) * step
    return np.arange(data_min, data_max + step, step)


def determine_hist_bins_auto(arr: np.ndarray) -> np.ndarray | int:
    """Determine appropriate histogram bin count from array dtype.

    - Floating dtype: 256 bins
    - Integer dtype: full value span (max - min + 1)
    """
    if np.issubdtype(arr.dtype, np.floating):
        bins = 1000
        if True:
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
            bins = np.arange(data_min, data_max, step)  # ヒストグラムを1.0刻みでプロット
        return bins
    data_min = arr.min()
    data_max = arr.max()
    return max(1, int(data_max - data_min) + 1)


def histogram_series(arr: np.ndarray, *, bins: np.ndarray | None = None) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Compute per-channel histogram series.

    Returns a mapping label -> (xs, counts).
    Labels:
      - Color: 'C{index}' per channel
      - Grayscale: 'I'
    """
    if bins is None:
        # 複数画像解析用
        bins = determine_hist_bins_auto(arr)

    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    if arr.ndim == 3 and arr.shape[2] > 1:
        nch = arr.shape[2]
        for c in range(nch):
            data = arr[:, :, c].ravel()
            if np.issubdtype(data.dtype, np.integer):
                data_min = arr.min()
                data_max = arr.max()
                hist, edges = np.histogram(data, bins=bins, range=(data_min, data_max + 1))
                xs = edges[:-1]
            else:
                hist, edges = np.histogram(data, bins=bins)
                xs = (edges[:-1] + edges[1:]) / 2.0
            out[f"C{c}"] = (xs, hist)
    else:
        gray = arr if arr.ndim == 2 else arr[:, :, 0]
        data = gray.ravel()
        if np.issubdtype(data.dtype, np.integer):
            data_min = arr.min()
            data_max = arr.max()
            hist, edges = np.histogram(data, bins=bins, range=(data_min, data_max + 1))
            xs = edges[:-1]
        else:
            hist, edges = np.histogram(data, bins=bins)
            xs = (edges[:-1] + edges[1:]) / 2.0
        out["I"] = (xs, hist)
    return out


def ecdf_series(arr: np.ndarray, *, max_points: int = 2000) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Compute per-channel ECDF with fast downsampling."""

    def _calc_fast_ecdf(data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        data = data.ravel()
        n_samples = len(data)

        if n_samples > max_points:
            # np.random.choice よりスライス（ストライド抽出）の方が高速
            step = n_samples // max_points
            data = data[::step][:max_points]

        xs = np.sort(data)
        # 0.0 ~ 1.0 の累積確率
        ys = np.linspace(1.0 / len(xs), 1.0, len(xs))
        return xs, ys

    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    if arr.ndim == 3 and arr.shape[2] > 1:
        for c in range(arr.shape[2]):
            out[f"C{c}"] = _calc_fast_ecdf(arr[:, :, c])
    else:
        gray = arr if arr.ndim == 2 else arr[:, :, 0]
        out["I"] = _calc_fast_ecdf(gray)

    return out


def compute_profile_1d(channel_data: np.ndarray, orientation: str, method: str = "mean") -> np.ndarray:
    """Compute 1D profile for a single-channel 2D array.

    orientation: 'h' (horizontal), 'v' (vertical)
    method: `mean`, 'std', 'min', 'max', 'p2p', 'median'
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
    """Compute per-channel profile series (y-values only).

    Returns a mapping label -> profile array.
    Labels:
      - Color: 'C{index}' per channel
      - Grayscale: 'I'
    """
    out: dict[str, np.ndarray] = {}
    if arr.ndim == 3 and arr.shape[2] > 1:
        nch = arr.shape[2]
        for c in range(nch):
            prof = compute_profile_1d(arr[:, :, c], orientation, method)
            out[f"C{c}"] = prof
    else:
        gray = arr if arr.ndim == 2 else arr[:, :, 0]
        prof = compute_profile_1d(gray, orientation, method)
        out["I"] = prof
    return out


def get_profile_offset(image_rect, orientation: str) -> int:
    """Get x-axis offset for absolute mode given a QRect-like object.

    image_rect: object with x(), y() methods (Qt QRect)
    """
    if image_rect is None:
        return 0
    if orientation == "h":
        return int(image_rect.x())
    if orientation == "v":
        return int(image_rect.y())
    return int(min(image_rect.x(), image_rect.y()))


# --- Statistics helpers ---


def calc_stats(data: np.ndarray) -> tuple[float, float, float, float, float]:
    if data.size == 0:
        mean = std = median = min = max = np.nan
    else:
        mean = np.mean(data)
        std = np.std(data)
        median = np.median(data)
        min = np.min(data)
        max = np.max(data)
        fano = std**2 / mean
    return mean, std, median, min, max, fano


def histogram_stats(arr: np.ndarray, channel_checks: list[bool] | None = None):
    """Return per-channel stats for histogram display.

    Returns list of dicts: { 'ch': label, 'mean':, 'std':, 'median':, 'min':, 'max':, 'is_int': bool }
    Only includes channels where channel_checks[c] is True (if provided).
    """
    results = []
    if arr.ndim == 3 and arr.shape[2] > 1:
        nch = arr.shape[2]
        checks = channel_checks or [True] * nch
        for c in range(nch):
            if c < len(checks) and not checks[c]:
                continue
            data = arr[:, :, c].ravel()
            mean_v, std_v, median_v, min_v, max_v, fano_v = calc_stats(data)
            results.append(
                {
                    "ch": str(c),  # numeric index for legacy consumers
                    "curve_label": f"C{c}",  # explicit channel label used for color mapping
                    "mean": mean_v,
                    "std": std_v,
                    "median": median_v,
                    "min": min_v,
                    "max": max_v,
                    "fano": fano_v,
                    "is_int": bool(np.issubdtype(data.dtype, np.integer)),
                }
            )
    else:
        gray = arr if arr.ndim == 2 else arr[:, :, 0]
        data = gray.ravel()
        mean_v, std_v, median_v, min_v, max_v, fano_v = calc_stats(data)
        results.append(
            {
                "ch": "0",
                "curve_label": "I",  # intensity label
                "mean": mean_v,
                "std": std_v,
                "median": median_v,
                "min": min_v,
                "max": max_v,
                "fano": fano_v,
                "is_int": bool(np.issubdtype(gray.dtype, np.integer)),
            }
        )
    return results


def profile_stats(
    arr: np.ndarray, *, orientation: str = "h", method: str = "mean", channel_checks: list[bool] | None = None
):
    """Return per-channel stats for profile display based on computed profiles."""
    results = []
    if arr.ndim == 3 and arr.shape[2] > 1:
        nch = arr.shape[2]
        checks = channel_checks or [True] * nch
        for c in range(nch):
            if c < len(checks) and not checks[c]:
                continue
            prof = compute_profile_1d(arr[:, :, c], orientation, method)
            mean_v, std_v, median_v, min_v, max_v, fano_v = calc_stats(prof)
            results.append(
                {
                    "ch": str(c),
                    "curve_label": f"C{c}",
                    "mean": mean_v,
                    "std": std_v,
                    "median": median_v,
                    "min": min_v,
                    "max": max_v,
                    "fano": fano_v,
                    "is_int": bool(np.issubdtype(arr[:, :, c].dtype, np.integer)),
                }
            )
    else:
        gray = arr if arr.ndim == 2 else arr[:, :, 0]
        prof = compute_profile_1d(gray, orientation, method)
        mean_v, std_v, median_v, min_v, max_v, fano_v = calc_stats(prof)
        results.append(
            {
                "ch": "0",
                "curve_label": "I",
                "mean": mean_v,
                "std": std_v,
                "median": median_v,
                "min": min_v,
                "max": max_v,
                "fano": fano_v,
                "is_int": bool(np.issubdtype(gray.dtype, np.integer)) if prof.dtype else False,
            }
        )
    return results
