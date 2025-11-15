"""Application-wide constants for PixelScopeViewer.

This module contains shared constants used across the application.
"""

# Zoom scale limits
MIN_ZOOM_SCALE = 1.0 / 32.0  # 1/32x (0.03125)
MAX_ZOOM_SCALE = 64.0  # 64x

# Brightness gain limits (matching zoom range for consistency)
MIN_BRIGHTNESS_GAIN = 1.0 / 128.0  # 1/128x
MAX_BRIGHTNESS_GAIN = 128.0  # 128x
