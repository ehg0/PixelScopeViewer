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
    QMenuBar,
)
from PySide6.QtCore import Qt, Signal, QRect
from PySide6.QtGui import QShortcut, QKeySequence, QGuiApplication

from .selection_dialog import TileSelectionDialog
from .tile_widget import TileWidget
from .brightness_dialog import TilingBrightnessDialog
from .help_dialog import TilingHelpDialog
from PixelScopeViewer.core.image_io import numpy_to_qimage
from PixelScopeViewer.core.constants import MIN_ZOOM_SCALE, MAX_ZOOM_SCALE


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
        self.setFocusPolicy(Qt.StrongFocus)
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
        self._is_fit_zoom = False
        self._previous_zoom = 1.0
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

        # Set focus to dialog for keyboard input
        self.setFocus()

    def _build_ui(self):
        """Build the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Menu bar
        menu_bar = QMenuBar(self)

        # File menu
        file_menu = menu_bar.addMenu("ファイル(&F)")
        change_images_action = file_menu.addAction("比較画像変更(&C)...")
        change_images_action.triggered.connect(self.change_comparison_images)

        # View menu
        view_menu = menu_bar.addMenu("表示(&V)")
        brightness_action = view_menu.addAction("輝度調整(&B)...")
        brightness_action.triggered.connect(self.show_brightness_dialog)

        # Help menu
        help_menu = menu_bar.addMenu("ヘルプ(&H)")
        help_action = help_menu.addAction("キーボードショートカット(&K)")
        help_action.triggered.connect(self.show_help)
        layout.setMenuBar(menu_bar)

        # Grid layout for tiles
        grid_widget = QWidget()
        self.grid_layout = QGridLayout(grid_widget)
        self.grid_layout.setSpacing(4)

        layout.addWidget(grid_widget, 1)

        # Status bar with multiple sections
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("font-size: 11pt;")
        # Left side: mouse coordinates and ROI
        self.mouse_coords_label = QLabel()
        self.roi_info_label = QLabel()
        # Right side: brightness and scale
        self.brightness_label = QLabel()
        self.scale_label = QLabel()

        self.status_bar.addWidget(self.mouse_coords_label)
        self.status_bar.addWidget(self.roi_info_label)
        self.status_bar.addWidget(QLabel(""), 1)  # Spacer
        self.status_bar.addPermanentWidget(self.brightness_label)
        self.status_bar.addPermanentWidget(self.scale_label)
        layout.addWidget(self.status_bar)

        # Store current mouse coordinates for status bar
        self.current_mouse_coords = None

        # Setup shortcuts
        self._setup_shortcuts()

        # Create initial tiles
        self._rebuild_tiles()

    def _clear_tiles(self):
        """Clear all existing tiles from the grid."""
        # Disconnect and remove all tiles
        for tile in self.tiles:
            # Disconnect signals
            try:
                tile.activated.disconnect()
                tile.roi_changed.disconnect()
                tile.image_label.hover_info.disconnect()
                if tile.scroll_area.horizontalScrollBar():
                    tile.scroll_area.horizontalScrollBar().sliderMoved.disconnect()
                if tile.scroll_area.verticalScrollBar():
                    tile.scroll_area.verticalScrollBar().sliderMoved.disconnect()
            except:
                pass

            # Remove from grid
            self.grid_layout.removeWidget(tile)
            tile.setParent(None)
            tile.deleteLater()

        # Clear lists
        self.tiles.clear()
        self.tile_dtype_groups.clear()
        self.displayed_image_data.clear()

        # Clear ROI
        self.common_roi_rect = None

    def _rebuild_tiles(self):
        """Rebuild tiles based on current selection."""
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
            tile.mouse_coords_changed.connect(self._on_mouse_coords_changed)

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

        # Set initial active tile
        if self.tiles:
            self.set_active_tile(0)

        # Update display
        self.update_status_bar()

    def change_comparison_images(self):
        """Show selection dialog to change comparison images."""
        # Show selection dialog
        selection_dialog = TileSelectionDialog(self, self.all_images)

        # Pre-select current grid size in combo box
        for idx in range(selection_dialog.grid_combo.count()):
            if selection_dialog.grid_combo.itemData(idx) == self.grid_size:
                selection_dialog.grid_combo.setCurrentIndex(idx)
                break

        # Pre-check currently selected images
        for idx in self.selected_indices:
            if idx < selection_dialog.image_list_widget.count():
                item = selection_dialog.image_list_widget.item(idx)
                if item:
                    item.setCheckState(Qt.Checked)

        if selection_dialog.exec() != QDialog.Accepted:
            return

        grid_size, selected_indices = selection_dialog.get_selection()
        if not selected_indices:
            QMessageBox.warning(self, "比較画像変更", "画像が選択されていません。")
            return

        # Update settings
        self.grid_size = grid_size
        self.selected_indices = selected_indices

        # Rebuild tiles
        self._clear_tiles()
        self._rebuild_tiles()

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
        # Help
        QShortcut(QKeySequence("F1"), self).activated.connect(self.show_help)

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

        # Arrow key scrolling (synchronized)
        QShortcut(QKeySequence("Left"), self).activated.connect(lambda: self._scroll_by_key(-10, 0, False))
        QShortcut(QKeySequence("Right"), self).activated.connect(lambda: self._scroll_by_key(10, 0, False))
        QShortcut(QKeySequence("Up"), self).activated.connect(lambda: self._scroll_by_key(0, -10, False))
        QShortcut(QKeySequence("Down"), self).activated.connect(lambda: self._scroll_by_key(0, 10, False))
        QShortcut(QKeySequence("Shift+Left"), self).activated.connect(lambda: self._scroll_by_key(-50, 0, True))
        QShortcut(QKeySequence("Shift+Right"), self).activated.connect(lambda: self._scroll_by_key(50, 0, True))
        QShortcut(QKeySequence("Shift+Up"), self).activated.connect(lambda: self._scroll_by_key(0, -50, True))
        QShortcut(QKeySequence("Shift+Down"), self).activated.connect(lambda: self._scroll_by_key(0, 50, True))
        QShortcut(QKeySequence("Ctrl+C"), self).activated.connect(self.copy_active_tile_roi)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self).activated.connect(self.copy_all_tiles_roi_as_grid)

        # Tile rotation
        QShortcut(QKeySequence("Tab"), self).activated.connect(self.rotate_tiles_forward)
        QShortcut(QKeySequence("Shift+Tab"), self).activated.connect(self.rotate_tiles_backward)

        # Tile swapping
        QShortcut(QKeySequence("Ctrl+Shift+Right"), self).activated.connect(self.swap_with_next_tile)
        QShortcut(QKeySequence("Ctrl+Shift+Left"), self).activated.connect(self.swap_with_previous_tile)

    def adjust_zoom(self, factor, tile_index=None, mouse_pos=None):
        """Adjust zoom for all tiles.

        Args:
            factor: Zoom factor (2.0 for zoom in, 0.5 for zoom out)
            tile_index: Index of the tile that triggered the zoom (for mouse position)
            mouse_pos: Mouse position in viewport coordinates (for Ctrl+Wheel zoom)
        """
        # Use active tile if not specified
        if tile_index is None:
            tile_index = self.active_tile_index

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
        if hasattr(self, "_is_fit_zoom"):
            self._is_fit_zoom = False

        # Update all tiles with new zoom
        for tile in self.tiles:
            tile.set_zoom(self.scale)

        # Wait for GUI to update scrollbar ranges after zoom change
        from PySide6.QtWidgets import QApplication

        QApplication.processEvents()

        # Calculate new scroll position to keep the target point at the same viewport position
        # After zoom, the image point should be at: new_scroll + viewport_offset = image_coord * new_scale
        new_scroll_x = image_x * self.scale - viewport_x
        new_scroll_y = image_y * self.scale - viewport_y

        # Apply scroll position to ALL tiles (not just source, to avoid sync issues)
        self._syncing_scroll = True
        try:
            for i, tile in enumerate(self.tiles):
                tile_hsb = tile.scroll_area.horizontalScrollBar()
                tile_vsb = tile.scroll_area.verticalScrollBar()

                if tile_hsb:
                    clamped_x = max(tile_hsb.minimum(), min(new_scroll_x, tile_hsb.maximum()))
                    tile_hsb.setValue(int(clamped_x))
                if tile_vsb:
                    clamped_y = max(tile_vsb.minimum(), min(new_scroll_y, tile_vsb.maximum()))
                    tile_vsb.setValue(int(clamped_y))
        finally:
            self._syncing_scroll = False

        # Process events to ensure all scroll positions are applied
        QApplication.processEvents()

        self.update_status_bar()

    def toggle_fit_zoom(self):
        """Toggle between fit-to-window and original zoom."""
        if not self.tiles:
            return

        # Check if currently at fit zoom
        if hasattr(self, "_is_fit_zoom") and self._is_fit_zoom:
            # Return to previous zoom
            if hasattr(self, "_previous_zoom"):
                self.scale = self._previous_zoom
            else:
                self.scale = 1.0
            self._is_fit_zoom = False
        else:
            # Save current zoom and fit to window
            self._previous_zoom = self.scale

            # Calculate fit zoom based on scroll area size and image size
            active_tile = (
                self.tiles[self.active_tile_index] if self.active_tile_index < len(self.tiles) else self.tiles[0]
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
                self.scale = min(scale_w, scale_h, 1.0)  # Don't zoom beyond 1.0
            else:
                self.scale = 1.0

            self._is_fit_zoom = True

        # Apply zoom to all tiles
        for tile in self.tiles:
            tile.set_zoom(self.scale)

        # Re-sync after zoom change
        if 0 <= self.active_tile_index < len(self.tiles):
            src_area = self.tiles[self.active_tile_index].scroll_area
            hsb = src_area.horizontalScrollBar()
            vsb = src_area.verticalScrollBar()
            if hsb:
                self.sync_scroll(self.active_tile_index, "h", hsb.value())
            if vsb:
                self.sync_scroll(self.active_tile_index, "v", vsb.value())

        self.update_status_bar()

    def adjust_gain(self, factor):
        """Adjust gain (all tiles) using binary steps (powers of 2).

        Args:
            factor: Multiplication factor (2.0 for increase, 0.5 for decrease)
        """
        # Apply factor
        self.brightness_gain *= factor

        # Snap to nearest power of 2 for clean binary steps
        import math

        if self.brightness_gain > 0:
            power = round(math.log2(self.brightness_gain))
            self.brightness_gain = 2.0**power

        # Clamp to reasonable range (1/128x to 128x, matching zoom range)
        min_gain = 1.0 / 128.0
        max_gain = 128.0
        self.brightness_gain = max(min_gain, min(self.brightness_gain, max_gain))

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

    def show_help(self):
        """Show help dialog with keyboard shortcuts."""
        if not hasattr(self, "_help_dialog") or self._help_dialog is None:
            self._help_dialog = TilingHelpDialog(self)

        self._help_dialog.show()
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()

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

    def _on_mouse_coords_changed(self, coords):
        """Handle mouse coordinates change from a tile.

        Args:
            coords: Tuple of (ix, iy) or None
        """
        self.current_mouse_coords = coords
        self.update_status_bar()

        # Update pixel values for all tiles at the same coordinate
        if coords is not None:
            ix, iy = coords
            for tile in self.tiles:
                arr = tile.get_displayed_array()
                if arr is not None:
                    try:
                        val = arr[iy, ix]
                        if isinstance(val, np.ndarray) or (
                            hasattr(val, "shape") and len(getattr(val, "shape", ())) > 0
                        ):
                            flat = np.array(val).ravel().tolist()
                            preview = ", ".join(str(x) for x in flat[:4])
                            text = f"[{preview}{', …' if len(flat) > 4 else ''}]"
                        else:
                            text = str(val)
                        # Truncate overly long text
                        if len(text) > 60:
                            text = text[:57] + "…"
                        tile.update_status(text)
                    except Exception:
                        tile.update_status("")
                else:
                    tile.update_status("")
        else:
            # Clear all tile pixel value displays
            for tile in self.tiles:
                tile.update_status("")

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

        # Update status bar to show ROI dimensions
        self.update_status_bar()

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

    def copy_all_tiles_roi_as_grid(self):
        """Copy ROI regions from all tiles arranged in grid layout to clipboard."""
        if not self.tiles:
            return

        roi_rect = self.common_roi_rect
        if not roi_rect or roi_rect.isEmpty():
            # No ROI set, do nothing
            return

        x, y, w, h = roi_rect.x(), roi_rect.y(), roi_rect.width(), roi_rect.height()
        rows, cols = self.grid_size

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
        # Left side: Mouse coordinates
        if self.current_mouse_coords:
            ix, iy = self.current_mouse_coords
            self.mouse_coords_label.setText(f"x={ix} y={iy}")
        else:
            self.mouse_coords_label.setText("")

        # Left side: ROI info
        if self.common_roi_rect and not self.common_roi_rect.isEmpty():
            r = self.common_roi_rect
            x0, y0 = r.x(), r.y()
            x1, y1 = x0 + r.width() - 1, y0 + r.height() - 1
            roi_text = f" | ({x0}, {y0}) - ({x1}, {y1}), w: {r.width()}, h: {r.height()}"
            self.roi_info_label.setText(roi_text)
        else:
            self.roi_info_label.setText("")

        # Right side: Brightness parameters
        brightness_parts = [f"Gain: {self.brightness_gain:.2f}"]

        # Count tiles per dtype
        dtype_counts = {}
        for dtype_group in self.tile_dtype_groups:
            dtype_counts[dtype_group] = dtype_counts.get(dtype_group, 0) + 1

        # Add dtype info
        for dtype_group in sorted(dtype_counts.keys()):
            count = dtype_counts[dtype_group]
            params = self.brightness_params_by_dtype[dtype_group]
            if dtype_group == "float":
                brightness_parts.append(
                    f"{dtype_group}({count}): off={params['offset']:.2f} sat={params['saturation']:.2f}"
                )
            else:
                brightness_parts.append(f"{dtype_group}({count}): off={params['offset']} sat={params['saturation']}")

        self.brightness_label.setText(" | ".join(brightness_parts))

        # Right side: Scale
        self.scale_label.setText(f" | Scale: {self.scale:.2f}x")

    def _scroll_by_key(self, dx: int, dy: int, is_shift: bool):
        """Scroll all tiles synchronously by arrow keys.

        Args:
            dx: Horizontal scroll delta (positive = right)
            dy: Vertical scroll delta (positive = down)
            is_shift: Whether Shift modifier is pressed
        """
        if not self.tiles or self.active_tile_index >= len(self.tiles):
            return

        active_tile = self.tiles[self.active_tile_index]
        scroll_area = active_tile.scroll_area

        # Apply horizontal scroll
        if dx != 0:
            hsb = scroll_area.horizontalScrollBar()
            if hsb:
                new_val = hsb.value() + dx
                new_val = max(hsb.minimum(), min(hsb.maximum(), new_val))
                hsb.setValue(new_val)
                self.sync_scroll(self.active_tile_index, "h", new_val)

        # Apply vertical scroll
        if dy != 0:
            vsb = scroll_area.verticalScrollBar()
            if vsb:
                new_val = vsb.value() + dy
                new_val = max(vsb.minimum(), min(vsb.maximum(), new_val))
                vsb.setValue(new_val)
                self.sync_scroll(self.active_tile_index, "v", new_val)
