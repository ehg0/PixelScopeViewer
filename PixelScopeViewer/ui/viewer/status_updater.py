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

        # Update title bar with filename and index
        filename = Path(p).name
        img = self.viewer.images[self.viewer.current_index]
        arr = img.get("base_array", img.get("array"))
        if arr.ndim == 2:
            h, w = arr.shape
            c = 1
        else:
            h, w, c = arr.shape[:3]
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

    def update_roi_status(self, rect=None):
        """Update status bar with ROI rectangle information.

        Args:
            rect: ROI rectangle (QRect, None uses current ROI)
        """
        # Prefer the canonical image-coordinate ROI for consistent display
        if self.viewer.current_roi_rect is not None and not self.viewer.current_roi_rect.isNull():
            x0 = self.viewer.current_roi_rect.x()
            y0 = self.viewer.current_roi_rect.y()
            w = self.viewer.current_roi_rect.width()
            h = self.viewer.current_roi_rect.height()
            x1 = x0 + w - 1
            y1 = y0 + h - 1
            self.viewer.status_roi.setText(f"({x0}, {y0}) - ({x1}, {y1}), w: {w}, h: {h}")
            return
        # Fallback: derive from provided label-rect when current ROI is missing
        if rect is None or rect.isNull():
            self.viewer.status_roi.setText("")
            return
        s = self.viewer.scale if hasattr(self.viewer, "scale") else 1.0
        x0 = int(rect.left() / s)
        y0 = int(rect.top() / s)
        x1 = int(rect.right() / s)
        y1 = int(rect.bottom() / s)
        w = x1 - x0 + 1
        h = y1 - y0 + 1
        self.viewer.status_roi.setText(f"({x0}, {y0}) - ({x1}, {y1}), w: {w}, h: {h}")
