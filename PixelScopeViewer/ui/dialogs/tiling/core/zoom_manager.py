"""Zoom management for tiling comparison."""

from typing import List, Optional
from PySide6.QtWidgets import QApplication
from PixelScopeViewer.core.constants import MIN_ZOOM_SCALE, MAX_ZOOM_SCALE
import numpy as np


class ZoomManager:
    """Manages zoom operations for all tiles."""

    def __init__(self, tiles: List, get_active_tile_index_func):
        """Initialize zoom manager.

        Args:
            tiles: List of TileWidget instances
            get_active_tile_index_func: Function to get the active tile index
        """
        self.tiles = tiles
        self.get_active_tile_index = get_active_tile_index_func
        self.scale = 1.0
        self._is_fit_zoom = False
        self._previous_zoom = 1.0

    def adjust_zoom(self, factor: float, tile_index: Optional[int] = None, mouse_pos=None):
        """Adjust zoom for all tiles.

        Args:
            factor: Zoom factor (2.0 for zoom in, 0.5 for zoom out)
            tile_index: Index of the tile that triggered the zoom (for mouse position)
            mouse_pos: Mouse position in viewport coordinates (for Ctrl+Wheel zoom)
        """
        # Use active tile if not specified
        if tile_index is None:
            tile_index = self.get_active_tile_index()

        if not (0 <= tile_index < len(self.tiles)):
            return

        source_tile = self.tiles[tile_index]
        scroll_area = source_tile.scroll_area
        viewport = scroll_area.viewport()

        # Calculate the point to keep fixed during zoom
        if mouse_pos is not None:
            # Mouse wheel: use mouse position in viewport
            viewport_x = mouse_pos.x()
            viewport_y = mouse_pos.y()
        else:
            # Keyboard (+/-): use viewport center
            viewport_x = viewport.width() / 2.0
            viewport_y = viewport.height() / 2.0

        # Convert viewport position to image coordinates (before zoom)
        hsb = scroll_area.horizontalScrollBar()
        vsb = scroll_area.verticalScrollBar()
        scroll_x = hsb.value() if hsb else 0
        scroll_y = vsb.value() if vsb else 0

        # Calculate image coordinates at the target viewport point
        image_x = (scroll_x + viewport_x) / self.scale
        image_y = (scroll_y + viewport_y) / self.scale

        # Apply new zoom (use same limits as main viewer)
        old_scale = self.scale
        self.scale *= factor
        # Use zoom limits from main viewer (MIN_ZOOM_SCALE, MAX_ZOOM_SCALE)
        self.scale = max(MIN_ZOOM_SCALE, min(self.scale, MAX_ZOOM_SCALE))

        # Manual zoom adjustment exits fit mode
        self._is_fit_zoom = False

        # Update all tiles with new zoom
        for tile in self.tiles:
            tile.set_zoom(self.scale)

        # Wait for GUI to update scrollbar ranges after zoom change
        QApplication.processEvents()

        # Calculate new scroll position to keep the target point at the same viewport position
        # After zoom, the image point should be at: new_scroll + viewport_offset = image_coord * new_scale
        new_scroll_x = image_x * self.scale - viewport_x
        new_scroll_y = image_y * self.scale - viewport_y

        # Apply scroll position to ALL tiles (not just source, to avoid sync issues)
        return new_scroll_x, new_scroll_y

    def toggle_fit_zoom(self, sync_scroll_func):
        """Toggle between fit-to-window and original zoom.

        Args:
            sync_scroll_func: Function to synchronize scroll positions
        """
        if not self.tiles:
            return

        # Check if currently at fit zoom
        if self._is_fit_zoom:
            # Return to previous zoom
            self.scale = self._previous_zoom if hasattr(self, "_previous_zoom") else 1.0
            self._is_fit_zoom = False
        else:
            # Save current zoom and fit to window
            self._previous_zoom = self.scale

            # Calculate fit zoom based on scroll area size and image size
            active_tile = (
                self.tiles[self.get_active_tile_index()]
                if self.get_active_tile_index() < len(self.tiles)
                else self.tiles[0]
            )
            scroll_area = active_tile.scroll_area
            viewport = scroll_area.viewport()

            # Get image dimensions
            image_label = active_tile.image_label
            if image_label.qimage:
                img_width = image_label.qimage.width()
                img_height = image_label.qimage.height()
                viewport_width = viewport.width()
                viewport_height = viewport.height()

                # Calculate scale to fit both dimensions
                scale_w = viewport_width / img_width if img_width > 0 else 1.0
                scale_h = viewport_height / img_height if img_height > 0 else 1.0
                fit_scale = min(scale_w, scale_h, 1.0)  # Don't zoom beyond 1.0
                # Clamp to valid zoom range
                fit_scale = max(MIN_ZOOM_SCALE, min(MAX_ZOOM_SCALE, fit_scale))
                # Snap to nearest power of 2
                power = round(np.log2(fit_scale))
                self.scale = 2.0**power
            else:
                self.scale = 1.0

            self._is_fit_zoom = True

        # Apply zoom to all tiles
        for tile in self.tiles:
            tile.set_zoom(self.scale)

        # Re-sync after zoom change
        active_idx = self.get_active_tile_index()
        if 0 <= active_idx < len(self.tiles):
            src_area = self.tiles[active_idx].scroll_area
            hsb = src_area.horizontalScrollBar()
            vsb = src_area.verticalScrollBar()
            if hsb:
                sync_scroll_func(active_idx, "h", hsb.value())
            if vsb:
                sync_scroll_func(active_idx, "v", vsb.value())

    def get_scale(self) -> float:
        """Get current zoom scale."""
        return self.scale

    def is_fit_zoom(self) -> bool:
        """Check if in fit zoom mode."""
        return self._is_fit_zoom
