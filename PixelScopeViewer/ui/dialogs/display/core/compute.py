"""Brightness computation functions (Qt-independent).

This module provides pure functions for applying brightness adjustments
to image arrays.
"""

import numpy as np


def apply_brightness_adjustment(arr: np.ndarray, offset: float, gain: float, saturation: float) -> np.ndarray:
    """Apply brightness adjustment to an image array.

    Formula:
        yout = gain * (yin - offset) / saturation * 255

    Parameters
    ----------
    arr : np.ndarray
        Input image array (accepts any dtype)
    offset : float
        Intensity baseline shift (can be negative)
    gain : float
        Intensity amplification factor (positive only)
    saturation : float
        Maximum intensity reference (positive only)

    Returns
    -------
    np.ndarray
        Adjusted array clipped to [0, 255] and converted to uint8

    Notes
    -----
    If saturation is 0, returns the original array to avoid division by zero.
    """
    # Avoid division by zero
    if saturation == 0:
        return arr

    # Apply formula with proper type conversion
    adjusted = gain * (arr.astype(np.float32) - offset) / saturation * 255

    # Clip to valid range and convert back to uint8
    return np.clip(adjusted, 0, 255).astype(np.uint8)


def apply_brightness_adjustment_float(arr: np.ndarray, offset: float, gain: float, saturation: float) -> np.ndarray:
    """Apply linear brightness transform but keep float and sign (no clipping).

    Intended for vector fields (e.g., 2ch flow for HSV) where preserving
    angles and relative magnitudes is important. Performs:

        y = gain * (x - offset) / max(saturation, eps)

    without scaling to 0..255 or dtype conversion.

    Args:
        arr: Input image array (any dtype). Output is float32 with same shape.
        offset: Baseline shift.
        gain: Gain multiplier.
        saturation: Scale reference. If 0, returns original array as float32.

    Returns:
        np.ndarray: float32 array with linear transform applied, no clipping.
    """
    x = arr.astype(np.float32, copy=False)
    if saturation == 0:
        return x.copy()
    eps = 1e-12
    return gain * (x - offset) / max(float(saturation), eps)
