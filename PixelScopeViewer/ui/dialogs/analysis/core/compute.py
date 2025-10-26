"""Computation helpers for AnalysisDialog.

This module centralizes histogram/profile computations and related utilities
without depending on Qt. It is safe to import in non-Qt contexts.
"""

from __future__ import annotations

from typing import Dict, Tuple, Optional

import numpy as np


def determine_hist_bins(arr: np.ndarray) -> int:
    """Determine appropriate histogram bin count from array dtype.

    - Floating dtype: 256 bins
    - Integer dtype: full value span (max - min + 1)
    """
    if np.issubdtype(arr.dtype, np.floating):
        return 256
    data_min = arr.min()
    data_max = arr.max()
    return max(1, int(data_max - data_min) + 1)


def histogram_series(arr: np.ndarray, *, bins: Optional[int] = None) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
    """Compute per-channel histogram series.

    Returns a mapping label -> (xs, counts).
    Labels:
      - Color: 'C{index}' per channel
      - Grayscale: 'I'
    """
    if bins is None:
        bins = determine_hist_bins(arr)

    out: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    if arr.ndim == 3 and arr.shape[2] > 1:
        nch = arr.shape[2]
        for c in range(nch):
            data = arr[:, :, c].ravel()
            hist, edges = np.histogram(data, bins=bins)
            xs = (edges[:-1] + edges[1:]) / 2.0
            out[f"C{c}"] = (xs, hist)
    else:
        gray = arr if arr.ndim == 2 else arr[:, :, 0]
        hist, edges = np.histogram(gray.ravel(), bins=bins)
        xs = (edges[:-1] + edges[1:]) / 2.0
        out["I"] = (xs, hist)
    return out


def compute_profile_1d(channel_data: np.ndarray, orientation: str) -> np.ndarray:
    """Compute 1D profile for a single-channel 2D array.

    orientation: 'h' (horizontal), 'v' (vertical), or 'd' (diagonal)
    """
    if orientation == "h":
        return np.mean(channel_data, axis=0)
    if orientation == "v":
        return np.mean(channel_data, axis=1)

    # diagonal
    h, w = channel_data.shape
    if h == 0 or w == 0:
        return np.array([])
    if h == 1 and w == 1:
        return np.array([channel_data[0, 0]])
    if h == w:
        return np.diag(channel_data)
    diag_len = min(h, w)
    if diag_len == 1:
        return np.array([channel_data[0, 0]])
    y_coords = np.linspace(0, h - 1, diag_len, dtype=int)
    x_coords = np.linspace(0, w - 1, diag_len, dtype=int)
    return channel_data[y_coords, x_coords]


def profile_series(arr: np.ndarray, *, orientation: str = "h") -> Dict[str, np.ndarray]:
    """Compute per-channel profile series (y-values only).

    Returns a mapping label -> profile array.
    Labels:
      - Color: 'C{index}' per channel
      - Grayscale: 'I'
    """
    out: Dict[str, np.ndarray] = {}
    if arr.ndim == 3 and arr.shape[2] > 1:
        nch = arr.shape[2]
        for c in range(nch):
            prof = compute_profile_1d(arr[:, :, c], orientation)
            out[f"C{c}"] = prof
    else:
        gray = arr if arr.ndim == 2 else arr[:, :, 0]
        prof = compute_profile_1d(gray, orientation)
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


def _stats_1d(data: np.ndarray) -> Tuple[float, float, float, float, float]:
    mean_v = float(np.mean(data)) if data.size else 0.0
    std_v = float(np.std(data)) if data.size else 0.0
    median_v = float(np.median(data)) if data.size else 0.0
    min_v = float(np.min(data)) if data.size else 0.0
    max_v = float(np.max(data)) if data.size else 0.0
    return mean_v, std_v, median_v, min_v, max_v


def histogram_stats(arr: np.ndarray, channel_checks: Optional[list[bool]] = None):
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
            mean_v, std_v, median_v, min_v, max_v = _stats_1d(data)
            results.append(
                {
                    "ch": str(c),
                    "mean": mean_v,
                    "std": std_v,
                    "median": median_v,
                    "min": min_v,
                    "max": max_v,
                    "is_int": bool(np.issubdtype(data.dtype, np.integer)),
                }
            )
    else:
        gray = arr if arr.ndim == 2 else arr[:, :, 0]
        data = gray.ravel()
        mean_v, std_v, median_v, min_v, max_v = _stats_1d(data)
        results.append(
            {
                "ch": "0",
                "mean": mean_v,
                "std": std_v,
                "median": median_v,
                "min": min_v,
                "max": max_v,
                "is_int": bool(np.issubdtype(gray.dtype, np.integer)),
            }
        )
    return results


def profile_stats(arr: np.ndarray, *, orientation: str = "h", channel_checks: Optional[list[bool]] = None):
    """Return per-channel stats for profile display based on computed profiles."""
    results = []
    if arr.ndim == 3 and arr.shape[2] > 1:
        nch = arr.shape[2]
        checks = channel_checks or [True] * nch
        for c in range(nch):
            if c < len(checks) and not checks[c]:
                continue
            prof = compute_profile_1d(arr[:, :, c], orientation)
            mean_v, std_v, median_v, min_v, max_v = _stats_1d(prof)
            results.append(
                {
                    "ch": str(c),
                    "mean": mean_v,
                    "std": std_v,
                    "median": median_v,
                    "min": min_v,
                    "max": max_v,
                    "is_int": bool(np.issubdtype(arr[:, :, c].dtype, np.integer)),
                }
            )
    else:
        gray = arr if arr.ndim == 2 else arr[:, :, 0]
        prof = compute_profile_1d(gray, orientation)
        mean_v, std_v, median_v, min_v, max_v = _stats_1d(prof)
        results.append(
            {
                "ch": "0",
                "mean": mean_v,
                "std": std_v,
                "median": median_v,
                "min": min_v,
                "max": max_v,
                "is_int": bool(np.issubdtype(gray.dtype, np.integer)) if prof.size else False,
            }
        )
    return results
