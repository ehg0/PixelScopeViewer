"""ROI management for tiling comparison."""

import numpy as np
from typing import List, Optional, Tuple
from PySide6.QtCore import QRect, Signal
from PySide6.QtGui import QGuiApplication

from PixelScopeViewer.core.image_io import numpy_to_qimage


class ROIManager:
    """Manages ROI operations for all tiles."""

    def __init__(self, tiles: List, get_active_tile_index_func, common_roi_changed_signal: Signal):
        """Initialize ROI manager.

        Args:
            tiles: List of TileWidget instances
            get_active_tile_index_func: Function to get the active tile index
            common_roi_changed_signal: Signal to emit when ROI changes
        """
        self.tiles = tiles
        self.get_active_tile_index = get_active_tile_index_func
        self.common_roi_changed = common_roi_changed_signal
        self.common_roi_rect: Optional[QRect] = None

    def on_tile_roi_changed(self, roi_rect_in_image_coords: QRect):
        """Handle ROI change from a tile.

        Args:
            roi_rect_in_image_coords: ROI rectangle in image coordinates
        """
        self.common_roi_rect = roi_rect_in_image_coords
        self.common_roi_changed.emit(roi_rect_in_image_coords)

    def on_tile_roi_changed_list(self, roi_rect):
        """Handle ROI change signal from tile (list format).

        Args:
            roi_rect: ROI rectangle as list [x, y, w, h] or None
        """
        if roi_rect:
            self.common_roi_rect = QRect(roi_rect[0], roi_rect[1], roi_rect[2], roi_rect[3])
        else:
            self.common_roi_rect = None

        if self.common_roi_rect:
            self.common_roi_changed.emit(self.common_roi_rect)

    def sync_roi_to_all_tiles(self, roi_rect: QRect):
        """Sync ROI to all tiles.

        Args:
            roi_rect: ROI rectangle to sync
        """
        for i, tile in enumerate(self.tiles):
            is_active = i == self.get_active_tile_index()
            tile.set_roi_from_image_coords(roi_rect, is_active)

    def select_all_roi(self):
        """Select all (full image) for active tile."""
        if not self.tiles or self.get_active_tile_index() >= len(self.tiles):
            return

        active_tile = self.tiles[self.get_active_tile_index()]
        arr = active_tile.image_data["base_array"]
        h, w = arr.shape[:2]

        full_roi = QRect(0, 0, w, h)
        self.common_roi_rect = full_roi
        self.common_roi_changed.emit(full_roi)

    def clear_roi(self):
        """Clear ROI from all tiles."""
        self.common_roi_rect = None
        self.common_roi_changed.emit(QRect())

    def copy_active_tile_roi(self):
        """Copy ROI region from active tile to clipboard."""
        if not self.tiles or self.get_active_tile_index() >= len(self.tiles):
            return

        active_tile = self.tiles[self.get_active_tile_index()]
        roi_rect = self.common_roi_rect

        arr = active_tile.get_displayed_array()

        if roi_rect and not roi_rect.isEmpty():
            x, y, w, h = roi_rect.x(), roi_rect.y(), roi_rect.width(), roi_rect.height()
            h_arr, w_arr = arr.shape[:2]

            if x < w_arr and y < h_arr:
                x2 = min(x + w, w_arr)
                y2 = min(y + h, h_arr)
                sub_arr = arr[y:y2, x:x2]
                qimg = numpy_to_qimage(sub_arr)
            else:
                qimg = None
        else:
            qimg = numpy_to_qimage(arr)

        if qimg and not qimg.isNull():
            QGuiApplication.clipboard().setImage(qimg)

    def copy_all_tiles_roi_as_grid(self, grid_size: Tuple[int, int]):
        """Copy ROI regions from all tiles arranged in grid layout to clipboard.

        Args:
            grid_size: Tuple of (rows, cols)
        """
        if not self.tiles:
            return

        roi_rect = self.common_roi_rect
        if not roi_rect or roi_rect.isEmpty():
            # No ROI set, do nothing
            return

        x, y, w, h = roi_rect.x(), roi_rect.y(), roi_rect.width(), roi_rect.height()
        rows, cols = grid_size

        # Extract ROI regions from all tiles
        roi_images = []
        for tile in self.tiles:
            arr = tile.get_displayed_array()
            if arr is None:
                continue

            h_arr, w_arr = arr.shape[:2]
            if x < w_arr and y < h_arr:
                x2 = min(x + w, w_arr)
                y2 = min(y + h, h_arr)
                sub_arr = arr[y:y2, x:x2]
                roi_images.append(sub_arr)
            else:
                # ROI out of bounds, skip this tile
                roi_images.append(None)

        # Create grid image
        if not roi_images or all(img is None for img in roi_images):
            return

        # Determine output dimensions (use first valid ROI size)
        roi_h, roi_w = h, w
        for img in roi_images:
            if img is not None:
                roi_h, roi_w = img.shape[:2]
                break

        # Determine if images are color or grayscale
        is_color = False
        num_channels = 1
        for img in roi_images:
            if img is not None and len(img.shape) == 3:
                is_color = True
                num_channels = img.shape[2]
                break

        # Create output array
        output_h = rows * roi_h
        output_w = cols * roi_w
        if is_color:
            output_array = np.zeros(
                (output_h, output_w, num_channels), dtype=roi_images[0].dtype if roi_images[0] is not None else np.uint8
            )
        else:
            output_array = np.zeros(
                (output_h, output_w), dtype=roi_images[0].dtype if roi_images[0] is not None else np.uint8
            )

        # Place each ROI image in the grid
        for i, img in enumerate(roi_images):
            if img is None:
                continue

            row = i // cols
            col = i % cols
            y_start = row * roi_h
            x_start = col * roi_w

            img_h, img_w = img.shape[:2]
            y_end = min(y_start + img_h, output_h)
            x_end = min(x_start + img_w, output_w)

            if is_color and len(img.shape) == 2:
                # Convert grayscale to color
                img = np.stack([img] * num_channels, axis=2)
            elif not is_color and len(img.shape) == 3:
                # Convert color to grayscale
                img = img[:, :, 0]

            output_array[y_start:y_end, x_start:x_end] = img[: y_end - y_start, : x_end - x_start]

        # Convert to QImage and copy to clipboard
        qimg = numpy_to_qimage(output_array)
        if qimg and not qimg.isNull():
            QGuiApplication.clipboard().setImage(qimg)

    def get_roi_status(self) -> str:
        """Get ROI status text for status bar.

        Returns:
            ROI status text
        """
        if self.common_roi_rect and not self.common_roi_rect.isEmpty():
            r = self.common_roi_rect
            x0, y0 = r.x(), r.y()
            x1, y1 = x0 + r.width() - 1, y0 + r.height() - 1
            return f" | ({x0}, {y0}) - ({x1}, {y1}), w: {r.width()}, h: {r.height()}"
        return ""
