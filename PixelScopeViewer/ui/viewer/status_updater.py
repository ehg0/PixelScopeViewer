"""Status bar update logic for ImageViewer.

This module handles all status bar update operations including:
- Mouse position and pixel value display
- Overall image/scale status display
- Brightness parameter display
- ROI rectangle display
"""

from pathlib import Path
import numpy as np
from PySide6.QtCore import QRect


class StatusUpdater:
    """Manages status bar updates for the image viewer.

    This class handles formatting and updating various status bar widgets
    with current viewer state information.
    """

    def __init__(self, viewer):
        """Initialize status updater.

        Args:
            viewer: ImageViewer instance
        """
        self.viewer = viewer

    def update_mouse_status(self, pos):
        """Update status bar with pixel value at mouse position.

        Args:
            pos: Mouse position (QPoint)
        """
        if self.viewer.current_index is None or not self.viewer.images:
            self.viewer.status_pixel.setText("")
            self.viewer.current_mouse_image_coords = None
            return
        img = self.viewer.images[self.viewer.current_index]
        # prefer base_array (unshifted) for status display when available
        arr = img.get("base_array", img.get("array"))
        s = self.viewer.scale if self.viewer.scale > 0 else 1.0
        ix = int(pos.x() / s)
        iy = int(pos.y() / s)
        h, w = arr.shape[:2]
        if 0 <= iy < h and 0 <= ix < w:
            v = arr[iy, ix]

            def _format_scalar(x, dtype):
                try:
                    if np.issubdtype(dtype, np.floating):
                        xv = float(x)
                        # Format to 4 decimal places
                        return f"{xv:.3f}"
                    else:
                        return str(int(x))
                except Exception:
                    return str(x)

            if np.ndim(v) == 0:
                val_str = _format_scalar(v, arr.dtype)
            else:
                vals = [_format_scalar(x, arr.dtype) for x in np.ravel(v)]
                val_str = "(" + ",".join(vals) + ")"

            self.viewer.status_pixel.setText(f"x={ix} y={iy} val={val_str}")
            # Store current image coordinates for zoom centering
            self.viewer.current_mouse_image_coords = (ix, iy)
        else:
            self.viewer.status_pixel.setText("")
            self.viewer.current_mouse_image_coords = None

    def update_status(self):
        """Update status bar with current image info and brightness parameters."""
        if self.viewer.current_index is None:
            # Update title bar to show no image
            self.viewer.setWindowTitle("PixelScopeViewer")
            # still update scale display
            self.viewer.status_scale.setText(f"Scale: {self.viewer.scale:.2f}x")
            # clear brightness when no image
            self.viewer.status_brightness.setText("")
            return
        p = self.viewer.images[self.viewer.current_index]["path"]

        # Update title bar with filename, size, and index
        filename = Path(p).name
        img = self.viewer.images[self.viewer.current_index]
        arr = img.get("base_array", img.get("array"))
        if arr.ndim == 2:
            h, w = arr.shape
            c = 1
        else:
            h, w, c = arr.shape[:3]

        # Get file size
        file_size_str = ""
        try:
            file_size = Path(p).stat().st_size
            if file_size < 1024:
                file_size_str = f"{file_size}B"
            elif file_size < 1024 * 1024:
                file_size_str = f"{file_size / 1024:.1f}KB"
            elif file_size < 1024 * 1024 * 1024:
                file_size_str = f"{file_size / (1024 * 1024):.1f}MB"
            else:
                file_size_str = f"{file_size / (1024 * 1024 * 1024):.2f}GB"
        except Exception:
            file_size_str = ""

        if file_size_str:
            title = f"[{self.viewer.current_index+1}/{len(self.viewer.images)}]  {filename} ({file_size_str}) — {w}×{h}, {c}ch"
        else:
            title = f"[{self.viewer.current_index+1}/{len(self.viewer.images)}]  {filename} — {w}×{h}, {c}ch"
        self.viewer.setWindowTitle(title)

        # display current scale
        try:
            self.viewer.status_scale.setText(f"Scale: {self.viewer.scale:.2f}x")
        except Exception:
            self.viewer.status_scale.setText("")

        # Display brightness parameters instead of bit shift
        self.update_brightness_status()

    def update_brightness_status(self):
        """Update status bar with formatted brightness parameters.

        Adjusts decimal precision based on value magnitude (more decimals for smaller values).
        """
        try:
            # Format offset
            if isinstance(self.viewer.brightness_offset, (int, np.integer)):
                offset_str = str(self.viewer.brightness_offset)
            else:
                offset_str = f"{self.viewer.brightness_offset:.1f}"

            # Format gain - use more decimals for small values, fewer for large values
            if self.viewer.brightness_gain < 0.01:
                gain_str = f"{self.viewer.brightness_gain:.6f}"
            elif self.viewer.brightness_gain < 0.1:
                gain_str = f"{self.viewer.brightness_gain:.5f}"
            elif self.viewer.brightness_gain >= 100:
                gain_str = f"{self.viewer.brightness_gain:.1f}"
            else:
                gain_str = f"{self.viewer.brightness_gain:.2f}"

            # Format saturation
            if isinstance(self.viewer.brightness_saturation, (int, np.integer)):
                sat_str = str(self.viewer.brightness_saturation)
            else:
                sat_str = f"{self.viewer.brightness_saturation:.1f}"

            brightness_text = f"Offset: {offset_str}, Gain: {gain_str}, Sat: {sat_str}"
            self.viewer.status_brightness.setText(brightness_text)
        except Exception as e:
            self.viewer.status_brightness.setText("")
