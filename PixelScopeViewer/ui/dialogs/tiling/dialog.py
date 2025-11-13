"""Main tiling comparison dialog."""

import numpy as np
from pathlib import Path
from typing import List, Dict, Optional
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QWidget,
    QStatusBar,
    QLabel,
    QMessageBox,
)
from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QShortcut, QKeySequence, QGuiApplication

from .selection_dialog import TileSelectionDialog
from .tile_widget import TileWidget
from .brightness_dialog import TilingBrightnessDialog
from PixelScopeViewer.core.image_io import numpy_to_qimage


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


class TilingComparisonDialog(QDialog):
    """Dialog for comparing multiple images in a grid layout.

    Features:
    - Synchronized scroll/zoom/ROI across all tiles
    - Per-dtype brightness adjustment (Offset/Saturation)
    - Common Gain control
    - Tile rotation and swapping
    - Active tile management for ROI editing and copying
    """

    # Signals
    common_roi_changed = Signal(QRect)

    def __init__(self, parent, image_list: List[Dict]):
        """Initialize tiling comparison dialog.

        Args:
            parent: Parent widget (ImageViewer)
            image_list: List of image dictionaries from ImageViewer
        """
        super().__init__(None)
        self.setWindowTitle("タイリング比較")
        self.parent_viewer = parent
        self.all_images = image_list

        # Show selection dialog first
        selection_dialog = TileSelectionDialog(self, image_list)
        if selection_dialog.exec() != QDialog.Accepted:
            # User cancelled
            self.reject()
            return

        grid_size, selected_indices = selection_dialog.get_selection()
        if not selected_indices:
            QMessageBox.warning(self, "タイリング比較", "画像が選択されていません。")
            self.reject()
            return

        self.grid_size = grid_size
        self.selected_indices = selected_indices

        # Brightness parameters
        self.brightness_gain = 1.0
        self.brightness_params_by_dtype = {
            "uint8": {"offset": 0, "saturation": 255},
            "uint16": {"offset": 0, "saturation": 1023},
            "float": {"offset": 0.0, "saturation": 1.0},
        }

        # Common state
        self.scale = 1.0
        self.common_roi_rect = None  # QRect in image coordinates
        self.active_tile_index = 0
        self._syncing_scroll = False

        # Tiles and their dtype groups
        self.tiles = []
        self.tile_dtype_groups = []
        self.displayed_image_data = []

        # Build UI
        self._build_ui()

        # Connect signals
        self.common_roi_changed.connect(self.sync_roi_to_all_tiles)

        # Set initial active tile
        if self.tiles:
            self.set_active_tile(0)

        # Resize dialog
        self.resize(1200, 800)

    def _build_ui(self):
        """Build the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Grid layout for tiles
        grid_widget = QWidget()
        self.grid_layout = QGridLayout(grid_widget)
        self.grid_layout.setSpacing(4)

        rows, cols = self.grid_size

        # Create tiles
        for i, img_idx in enumerate(self.selected_indices):
            if img_idx >= len(self.all_images):
                continue

            image_data = self.all_images[img_idx].copy()
            self.displayed_image_data.append(image_data)

            # Determine dtype group
            arr = image_data.get("base_array", image_data.get("array"))
            dtype_group = determine_dtype_group(arr)
            self.tile_dtype_groups.append(dtype_group)

            # Create tile widget
            tile = TileWidget(image_data, self, i)
            tile.activated.connect(lambda idx=i: self.set_active_tile(idx))
            tile.roi_changed.connect(self._on_tile_roi_changed)
            # Hover info -> status bar
            tile.image_label.hover_info.connect(lambda x, y, t, idx=i: self._on_hover_info(idx, x, y, t))

            self.tiles.append(tile)

            # Add to grid
            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(tile, row, col)

            # Initial display
            tile.update_display()
            # Connect scrollbars for sync - use ONLY sliderMoved to avoid signal conflicts
            if tile.scroll_area.horizontalScrollBar():
                hsb = tile.scroll_area.horizontalScrollBar()
                # sliderMoved: user dragging scrollbar thumb
                hsb.sliderMoved.connect(lambda val, idx=i: self._on_scroll(idx, "h", val, "sliderMoved"))
            if tile.scroll_area.verticalScrollBar():
                vsb = tile.scroll_area.verticalScrollBar()
                # sliderMoved: user dragging scrollbar thumb
                vsb.sliderMoved.connect(lambda val, idx=i: self._on_scroll(idx, "v", val, "sliderMoved"))

        layout.addWidget(grid_widget, 1)

        # Status bar
        self.status_bar = QStatusBar()
        self.status_label = QLabel()
        self.hover_label = QLabel()
        self.status_bar.addWidget(self.status_label, 1)
        self.status_bar.addPermanentWidget(self.hover_label)
        layout.addWidget(self.status_bar)

        # Setup shortcuts
        self._setup_shortcuts()

        # Initial display
        self.update_status_bar()

    def _on_scroll(self, source_index: int, direction: str, value: int, signal_name: str):
        """Handle scroll events with debug logging."""
        self.sync_scroll(source_index, direction, value)

    def _on_hover_info(self, tile_idx: int, ix: int, iy: int, value_text: str):
        """On hover in any tile, update all tiles' pixel value displays and show coordinates in status bar."""
        # Update each tile's pixel value display with value at (ix, iy)
        for i, data in enumerate(self.displayed_image_data):
            arr = data.get("base_array", data.get("array"))
            if arr is None:
                self.tiles[i].update_status("")
                continue
            h, w = arr.shape[:2]
            if 0 <= ix < w and 0 <= iy < h:
                try:
                    v = arr[iy, ix]
                    if hasattr(v, "shape") and len(getattr(v, "shape", ())) > 0:
                        flat = np.array(v).ravel().tolist()
                        preview = ", ".join(str(x) for x in flat[:4])
                        txt = f"[{preview}{', …' if len(flat) > 4 else ''}]"
                    else:
                        txt = str(v)
                    # Truncate if too long
                    if len(txt) > 50:
                        txt = txt[:47] + "…"
                except Exception:
                    txt = "NA"
            else:
                txt = ""
            self.tiles[i].update_status(txt)

        # Show only coordinates in status bar
        self.hover_label.setText(f"({ix}, {iy})")

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Zoom
        QShortcut(QKeySequence("+"), self).activated.connect(lambda: self.adjust_zoom(2.0))
        QShortcut(QKeySequence("-"), self).activated.connect(lambda: self.adjust_zoom(0.5))
        QShortcut(QKeySequence("f"), self).activated.connect(self.toggle_fit_zoom)

        # Gain
        QShortcut(QKeySequence("<"), self).activated.connect(lambda: self.adjust_gain(0.5))
        QShortcut(QKeySequence(">"), self).activated.connect(lambda: self.adjust_gain(2.0))

        # Brightness dialog
        QShortcut(QKeySequence("D"), self).activated.connect(self.show_brightness_dialog)

        # Reset
        QShortcut(QKeySequence("Ctrl+R"), self).activated.connect(self.reset_brightness)

        # ROI operations
        QShortcut(QKeySequence("Ctrl+A"), self).activated.connect(self.select_all_roi)
        QShortcut(QKeySequence("Esc"), self).activated.connect(self.clear_roi)
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(self.copy_active_tile_roi)

        # Tile rotation
        QShortcut(QKeySequence("Tab"), self).activated.connect(self.rotate_tiles_forward)
        QShortcut(QKeySequence("Shift+Tab"), self).activated.connect(self.rotate_tiles_backward)

        # Tile swapping
        QShortcut(QKeySequence("Ctrl+Shift+Right"), self).activated.connect(self.swap_with_next_tile)
        QShortcut(QKeySequence("Ctrl+Shift+Left"), self).activated.connect(self.swap_with_previous_tile)

    def adjust_zoom(self, factor):
        """Adjust zoom for all tiles."""
        self.scale *= factor
        self.scale = max(0.1, min(self.scale, 20.0))

        for tile in self.tiles:
            tile.set_zoom(self.scale)

        # After zoom changes, re-sync scroll positions using active tile as source
        if self.tiles and 0 <= self.active_tile_index < len(self.tiles):
            src_area = self.tiles[self.active_tile_index].scroll_area
            hsb = src_area.horizontalScrollBar()
            vsb = src_area.verticalScrollBar()
            if hsb:
                self.sync_scroll(self.active_tile_index, "h", hsb.value())
            if vsb:
                self.sync_scroll(self.active_tile_index, "v", vsb.value())

        self.update_status_bar()

    def toggle_fit_zoom(self):
        """Toggle between fit-to-window and original zoom."""
        # For scroll-based tiles, fit acts like reset zoom
        self.scale = 1.0
        for tile in self.tiles:
            tile.set_zoom(self.scale)
        # Re-sync after zoom reset
        if self.tiles and 0 <= self.active_tile_index < len(self.tiles):
            src_area = self.tiles[self.active_tile_index].scroll_area
            hsb = src_area.horizontalScrollBar()
            vsb = src_area.verticalScrollBar()
            if hsb:
                self.sync_scroll(self.active_tile_index, "h", hsb.value())
            if vsb:
                self.sync_scroll(self.active_tile_index, "v", vsb.value())
        self.update_status_bar()

    def adjust_gain(self, factor):
        """Adjust gain (all tiles)."""
        self.brightness_gain *= factor
        self.brightness_gain = max(0.1, min(self.brightness_gain, 10.0))

        self.refresh_all_tiles()
        self.update_status_bar()

    def reset_brightness(self):
        """Reset all brightness parameters."""
        self.brightness_gain = 1.0
        self.brightness_params_by_dtype = {
            "uint8": {"offset": 0, "saturation": 255},
            "uint16": {"offset": 0, "saturation": 1023},
            "float": {"offset": 0.0, "saturation": 1.0},
        }
        self.refresh_all_tiles()
        self.update_status_bar()

    def refresh_all_tiles(self):
        """Refresh display for all tiles."""
        for tile in self.tiles:
            tile.update_display()

    def refresh_tiles_by_dtype_group(self, dtype_group: str):
        """Refresh tiles of specific dtype group."""
        for i, tile in enumerate(self.tiles):
            if self.tile_dtype_groups[i] == dtype_group:
                tile.update_display()

    def show_brightness_dialog(self):
        """Show brightness adjustment dialog."""
        if not hasattr(self, "_brightness_dialog") or self._brightness_dialog is None:
            self._brightness_dialog = TilingBrightnessDialog(
                self, self.brightness_params_by_dtype, self.brightness_gain
            )
            self._brightness_dialog.brightness_changed.connect(self.on_brightness_dialog_changed)

        self._brightness_dialog.show()
        self._brightness_dialog.raise_()
        self._brightness_dialog.activateWindow()

    def on_brightness_dialog_changed(self, full_params: Dict):
        """Handle brightness change from dialog.

        Args:
            full_params: Dict mapping dtype groups to {gain, offset, saturation}
        """
        # Update gain from first entry (they're all the same)
        if full_params:
            first_group = list(full_params.keys())[0]
            self.brightness_gain = full_params[first_group]["gain"]

        # Update per-dtype params
        for dtype_group, params in full_params.items():
            self.brightness_params_by_dtype[dtype_group]["offset"] = params["offset"]
            self.brightness_params_by_dtype[dtype_group]["saturation"] = params["saturation"]

        self.refresh_all_tiles()
        self.update_status_bar()

    def set_active_tile(self, tile_index: int):
        """Set active tile."""
        if tile_index < 0 or tile_index >= len(self.tiles):
            return

        # Deactivate previous
        if 0 <= self.active_tile_index < len(self.tiles):
            self.tiles[self.active_tile_index].set_active(False)

        # Activate new
        self.active_tile_index = tile_index
        self.tiles[tile_index].set_active(True)

        # Update ROI display
        if self.common_roi_rect:
            self.sync_roi_to_all_tiles(self.common_roi_rect)

    def on_tile_roi_changed(self, roi_rect_in_image_coords: QRect):
        """Handle ROI change from a tile."""
        self.common_roi_rect = roi_rect_in_image_coords
        self.common_roi_changed.emit(roi_rect_in_image_coords)

    def _on_tile_roi_changed(self, roi_rect):
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

    def sync_scroll(self, source_index: int, direction: str, value: int):
        """Synchronize scrolls based on viewport-centered normalized position.

        Uses (value + pageStep/2) / (maximum + pageStep) to keep visible region aligned
        across different content sizes and viewport dimensions.
        """
        if self._syncing_scroll:
            return
        # Get source scrollbar and compute normalized center ratio
        src_sb = (
            self.tiles[source_index].scroll_area.horizontalScrollBar()
            if direction == "h"
            else self.tiles[source_index].scroll_area.verticalScrollBar()
        )
        if src_sb is None:
            return
        src_max = src_sb.maximum()
        src_page = src_sb.pageStep()
        denom = src_max + src_page
        if denom <= 0:
            # No scrollable range; do not force others
            return
        # value comes from signal; ensure consistent with src_sb.value()
        src_val = value
        # Center position ratio in [0,1]
        center_pos = src_val + (src_page / 2.0)
        ratio = max(0.0, min(1.0, center_pos / float(denom)))

        self._syncing_scroll = True
        try:
            for i, tile in enumerate(self.tiles):
                if i == source_index:
                    continue
                tgt_sb = (
                    tile.scroll_area.horizontalScrollBar() if direction == "h" else tile.scroll_area.verticalScrollBar()
                )
                if tgt_sb is None:
                    continue
                tgt_max = tgt_sb.maximum()
                tgt_page = tgt_sb.pageStep()
                tgt_denom = tgt_max + tgt_page
                if tgt_denom <= 0:
                    continue
                tgt_center = ratio * float(tgt_denom)
                tgt_val = int(round(tgt_center - (tgt_page / 2.0)))
                # Clamp to valid range
                if tgt_val < tgt_sb.minimum():
                    tgt_val = tgt_sb.minimum()
                if tgt_val > tgt_sb.maximum():
                    tgt_val = tgt_sb.maximum()

                # Skip if already at target value
                if tgt_sb.value() == tgt_val:
                    continue

                # Set value directly - _syncing_scroll flag prevents recursion
                # Do NOT use blockSignals as it prevents viewport updates
                tgt_sb.setValue(tgt_val)

                # Force the scroll area to process the change immediately
                tile.scroll_area.update()
                tile.scroll_area.viewport().update()
                # Process pending events to ensure scroll takes effect
                from PySide6.QtCore import QCoreApplication

                QCoreApplication.processEvents()

        finally:
            self._syncing_scroll = False

    def sync_roi_to_all_tiles(self, roi_rect: QRect):
        """Sync ROI to all tiles."""
        for i, tile in enumerate(self.tiles):
            is_active = i == self.active_tile_index
            tile.set_roi_from_image_coords(roi_rect, is_active)

    def select_all_roi(self):
        """Select all (full image) for active tile."""
        if not self.tiles or self.active_tile_index >= len(self.tiles):
            return

        active_tile = self.tiles[self.active_tile_index]
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
        if not self.tiles or self.active_tile_index >= len(self.tiles):
            return

        active_tile = self.tiles[self.active_tile_index]
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
            self.status_bar.showMessage(f"タイル{self.active_tile_index + 1}のROI領域をコピーしました", 2000)

    def rotate_tiles_forward(self):
        """Rotate tiles forward (right rotation)."""
        if len(self.tiles) < 2:
            return

        # Rotate image data
        last_data = self.displayed_image_data[-1]
        last_dtype = self.tile_dtype_groups[-1]

        self.displayed_image_data = [last_data] + self.displayed_image_data[:-1]
        self.tile_dtype_groups = [last_dtype] + self.tile_dtype_groups[:-1]

        for i, tile in enumerate(self.tiles):
            tile.set_image_data(self.displayed_image_data[i])

        self.active_tile_index = (self.active_tile_index + 1) % len(self.tiles)
        self._update_active_tile_visual()

    def rotate_tiles_backward(self):
        """Rotate tiles backward (left rotation)."""
        if len(self.tiles) < 2:
            return

        # Rotate image data
        first_data = self.displayed_image_data[0]
        first_dtype = self.tile_dtype_groups[0]

        self.displayed_image_data = self.displayed_image_data[1:] + [first_data]
        self.tile_dtype_groups = self.tile_dtype_groups[1:] + [first_dtype]

        for i, tile in enumerate(self.tiles):
            tile.set_image_data(self.displayed_image_data[i])

        self.active_tile_index = (self.active_tile_index - 1) % len(self.tiles)
        self._update_active_tile_visual()

    def swap_with_next_tile(self):
        """Swap active tile with next tile."""
        if len(self.tiles) < 2:
            return

        current_idx = self.active_tile_index
        next_idx = (current_idx + 1) % len(self.tiles)

        self.swap_tiles(current_idx, next_idx)
        self.set_active_tile(next_idx)

    def swap_with_previous_tile(self):
        """Swap active tile with previous tile."""
        if len(self.tiles) < 2:
            return

        current_idx = self.active_tile_index
        prev_idx = (current_idx - 1) % len(self.tiles)

        self.swap_tiles(current_idx, prev_idx)
        self.set_active_tile(prev_idx)

    def swap_tiles(self, index_a: int, index_b: int):
        """Swap two tiles."""
        if index_a == index_b:
            return

        if not (0 <= index_a < len(self.tiles) and 0 <= index_b < len(self.tiles)):
            return

        # Swap image data
        temp_data = self.displayed_image_data[index_a]
        temp_dtype = self.tile_dtype_groups[index_a]

        self.displayed_image_data[index_a] = self.displayed_image_data[index_b]
        self.tile_dtype_groups[index_a] = self.tile_dtype_groups[index_b]

        self.displayed_image_data[index_b] = temp_data
        self.tile_dtype_groups[index_b] = temp_dtype

        # Update displays
        self.tiles[index_a].set_image_data(self.displayed_image_data[index_a])
        self.tiles[index_b].set_image_data(self.displayed_image_data[index_b])

    def _update_active_tile_visual(self):
        """Update active tile visual state."""
        for i, tile in enumerate(self.tiles):
            tile.set_active(i == self.active_tile_index)

        if self.common_roi_rect:
            self.sync_roi_to_all_tiles(self.common_roi_rect)

    def update_status_bar(self):
        """Update status bar with current parameters."""
        status_parts = [f"Gain: {self.brightness_gain:.2f}"]

        # Count tiles per dtype
        dtype_counts = {}
        for dtype_group in self.tile_dtype_groups:
            dtype_counts[dtype_group] = dtype_counts.get(dtype_group, 0) + 1

        # Add dtype info
        for dtype_group in sorted(dtype_counts.keys()):
            count = dtype_counts[dtype_group]
            params = self.brightness_params_by_dtype[dtype_group]
            if dtype_group == "float":
                status_parts.append(
                    f"{dtype_group}({count}): off={params['offset']:.2f} sat={params['saturation']:.2f}"
                )
            else:
                status_parts.append(f"{dtype_group}({count}): off={params['offset']} sat={params['saturation']}")

        if self.common_roi_rect and not self.common_roi_rect.isEmpty():
            r = self.common_roi_rect
            status_parts.append(f"ROI: x={r.x()} y={r.y()} w={r.width()} h={r.height()}")

        self.status_label.setText(" | ".join(status_parts))

    def keyPressEvent(self, event):
        """Handle key press events."""
        # Forward arrow keys to active tile for ROI editing
        if self.tiles and 0 <= self.active_tile_index < len(self.tiles):
            if event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
                active_tile = self.tiles[self.active_tile_index]
                active_tile.image_label.keyPressEvent(event)
                return

        super().keyPressEvent(event)
