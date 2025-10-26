"""Core computation functions for display adjustments (Qt-independent).

This module provides pure computation functions for brightness
and contrast adjustments.
"""

from .compute import apply_brightness_adjustment

__all__ = ["apply_brightness_adjustment"]
