"""Color utility functions for channel visualization.

This module provides common color schemes for multi-channel image display.
"""

from PySide6.QtGui import QColor


def get_default_channel_colors(n_channels: int) -> list:
    """Get default colors for n channels using hybrid scheme.

    Color scheme:
    - 1 channel: White (grayscale)
    - 3 channels: RGB (Red, Green, Blue)
    - 4 channels: RGBIR-like (Red, Green, Blue, Gray)
    - 5+ channels: Evenly distributed hues from color wheel

    Args:
        n_channels: Number of channels

    Returns:
        List of QColor objects

    Examples:
        >>> colors = get_default_channel_colors(3)
        >>> [c.name() for c in colors]
        ['#ff0000', '#00ff00', '#0000ff']

        >>> colors = get_default_channel_colors(8)
        >>> len(colors)
        8
    """
    # 1 channel: White
    if n_channels == 1:
        return [QColor(255, 255, 255)]

    # 3 channels: RGB
    if n_channels == 3:
        return [QColor(255, 0, 0), QColor(0, 255, 0), QColor(0, 0, 255)]

    # 4 channels: RGBIR-like
    if n_channels == 4:
        return [QColor(255, 0, 0), QColor(0, 255, 0), QColor(0, 0, 255), QColor(127, 127, 127)]

    # 5+ channels: Color wheel distribution
    colors = []
    for i in range(n_channels):
        hue = int(360 * i / n_channels)  # Evenly distribute hues
        color = QColor.fromHsv(hue, 200, 255)  # Moderate saturation for better visibility
        colors.append(color)
    return colors
