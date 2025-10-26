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
