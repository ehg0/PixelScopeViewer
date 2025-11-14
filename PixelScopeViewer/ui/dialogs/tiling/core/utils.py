"""Utility functions for tiling comparison."""

import numpy as np


def determine_dtype_group(arr: np.ndarray) -> str:
    """Determine dtype group for brightness parameter management.

    Args:
        arr: Image array

    Returns:
        'uint8', 'uint16', or 'float'
    """
    dtype = arr.dtype

    if np.issubdtype(dtype, np.floating):
        return "float"
    elif np.issubdtype(dtype, np.integer):
        try:
            max_val = np.iinfo(dtype).max
            if max_val <= 255:
                return "uint8"
            else:
                return "uint16"
        except:
            return "uint8"
    else:
        return "uint8"
