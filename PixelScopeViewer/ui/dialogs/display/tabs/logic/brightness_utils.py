"""Utility functions for brightness calculations and conversions."""

import math

import numpy as np

from PixelScopeViewer.core.constants import get_dtype_defaults


def determine_dtype_defaults(image_array=None, image_path=None):
    """Determine default brightness parameters based on image type.

    Args:
        image_array: numpy array of the image (optional)
        image_path: path to the image file (optional)

    Returns:
        dict: Dictionary containing:
            - dtype_key: "uint8", "uint16", or "float"
            - is_float_type: bool
            - initial_offset: float
            - initial_gain: float
            - initial_upper_level: float
            - offset_range: tuple (min, max)
            - upper_level_range: tuple (min, max)
    """
    if image_array is None:
        return get_dtype_defaults("uint8")

    dtype = "float" if np.issubdtype(image_array.dtype, np.floating) else "uint8"
    return get_dtype_defaults(dtype)


def clamp_value(value, min_val, max_val):
    """Clamp a value to a range."""
    return max(min_val, min(max_val, value))


def slider_to_value(slider_value, is_float, multiplier=10):
    """Convert slider value to actual value.

    Args:
        slider_value: Integer slider position
        is_float: Whether the value should be treated as float
        multiplier: Multiplier for float values (default 10 for offset, 1000 for upper_level)

    Returns:
        Actual value (float or int)
    """
    if is_float:
        return slider_value / multiplier
    return slider_value


def value_to_slider(value, is_float, multiplier=10):
    """Convert actual value to slider value.

    Args:
        value: Actual value
        is_float: Whether the value is float type
        multiplier: Multiplier for float values

    Returns:
        Integer slider position
    """
    if is_float:
        return int(value * multiplier)
    return int(value)


def gain_to_log2(gain):
    """Convert gain value to log2 slider value.

    Args:
        gain: Gain value (power of 2)

    Returns:
        Integer log2 value
    """
    if gain <= 0:
        return 0
    return int(round(math.log2(gain)))


def log2_to_gain(log2_value):
    """Convert log2 slider value to gain.

    Args:
        log2_value: Integer log2 value

    Returns:
        Gain as power of 2
    """
    return 2**log2_value


def round_to_power_of_2(value, log2_min=-7, log2_max=10):
    """Round a value to the nearest power of 2 within range.

    Args:
        value: Value to round
        log2_min: Minimum log2 value
        log2_max: Maximum log2 value

    Returns:
        Nearest power of 2
    """
    if value <= 0:
        return 1.0

    log2_val = math.log2(value)
    nearest_log2 = round(log2_val)
    clamped_log2 = clamp_value(nearest_log2, log2_min, log2_max)
    return 2**clamped_log2


def format_value_label(value, is_float):
    """Format a value for display in label.

    Args:
        value: Value to format
        is_float: Whether to format as float

    Returns:
        Formatted string
    """
    if is_float:
        return f"{value:.5f}"
    return f"{int(value)}"


def format_gain_label(gain):
    """Format gain value for display.

    Args:
        gain: Gain value

    Returns:
        Formatted string with appropriate decimal places
    """
    if gain < 0.01:
        return f"{gain:.6f}"
    elif gain < 0.1:
        return f"{gain:.5f}"
    elif gain >= 100:
        return f"{gain:.1f}"
    else:
        return f"{gain:.2f}"
