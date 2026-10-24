"""Application-wide constants for PixelScopeViewer.

This module contains shared constants used across the application.
"""

# Zoom scale limits
MIN_ZOOM_SCALE: float = 1.0 / 32.0  # 1/32x (0.03125)
MAX_ZOOM_SCALE: float = 32.0  # 32x

# Brightness gain limits (matching zoom range for consistency)
MIN_BRIGHTNESS_GAIN: float = 1.0 / 128.0  # 1/128x
MAX_BRIGHTNESS_GAIN: float = 128.0  # 128x


# Brightness, get_dtype_defaults
DTYPE_DEFAULTS = {
    "float": {
        "dtype_key": "float",
        "is_float_type": True,
        "initial_offset": 0.0,
        "initial_gain": 1.0,
        "initial_upper_level": 1.0,
        "offset_range": (0.0, 1e5),
        "upper_level_range": (0.0, 1e5),
    },
    "uint8": {
        "dtype_key": "uint8",
        "is_float_type": False,
        "initial_offset": 0,
        "initial_gain": 1.0,
        "initial_upper_level": 255,
        "offset_range": (-255, 255),
        "upper_level_range": (0, 255),
    },
    "uint16": {
        "dtype_key": "uint16",
        "is_float_type": False,
        "initial_offset": 0,
        "initial_gain": 1.0,
        "initial_upper_level": 1023,
        "offset_range": (-32768, 32768),
        "upper_level_range": (1, 65535),
    },
}


def get_dtype_defaults(dtype_key: str) -> dict:
    """指定されたdtypeのデフォルト設定を取得（該当がない場合はfloatを返す）"""
    return DTYPE_DEFAULTS.get(dtype_key, DTYPE_DEFAULTS["uint8"]).copy()
