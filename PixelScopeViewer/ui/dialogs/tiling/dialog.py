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
from .core import (
    ZoomManager,
    BrightnessManager,
    ScrollManager,
    ROIManager,
    TileManager,
    determine_dtype_group,
)
from PixelScopeViewer.core.image_io import numpy_to_qimage
from PixelScopeViewer.core.constants import MIN_ZOOM_SCALE, MAX_ZOOM_SCALE


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
        # Enable maximize and minimize buttons
        self.setWindowFlags(Qt.Window | Qt.WindowMinMaxButtonsHint | Qt.WindowCloseButtonHint)
        self.setFocusPolicy(Qt.StrongFocus)
        self.parent_viewer = parent
        self.all_images = image_list

        # Track child dialogs for cleanup
        self._brightness_dialog = None
        self._help_dialog = None

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

        # Shortcuts list to keep references
        self.shortcuts = []

        # Store current mouse coordinates for status bar
        self.current_mouse_coords = None

        # Build UI first (creates grid_layout and labels)
        self._build_ui()

        # Initialize managers after UI is built
        self.tile_manager = TileManager(self.grid_layout)
        self.brightness_manager = None  # Created after tiles
        self.scroll_manager = None  # Created after tiles
        self.zoom_manager = None  # Created after tiles
        self.roi_manager = None  # Created after tiles

        # Create initial tiles
        self._rebuild_tiles()

        # Initialize managers with tiles
        self._initialize_managers()

        # Connect signals
        self.common_roi_changed.connect(self.roi_manager.sync_roi_to_all_tiles)

        # Set initial active tile
        if self.tile_manager.get_tiles():
            self.tile_manager.set_active_tile(0)

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

        # Setup shortcuts
        self._setup_shortcuts()

    def _initialize_managers(self):
        """Initialize managers after tiles are created."""
        tiles = self.tile_manager.get_tiles()
        tile_dtype_groups = self.tile_manager.get_tile_dtype_groups()

        self.brightness_manager = BrightnessManager(tiles, tile_dtype_groups)
        self.scroll_manager = ScrollManager(tiles)
        self.zoom_manager = ZoomManager(tiles, self.tile_manager.get_active_tile_index)
        self.roi_manager = ROIManager(tiles, self.tile_manager.get_active_tile_index, self.common_roi_changed)

    def _clear_tiles(self):
        """Clear all existing tiles from the grid."""
        self.tile_manager.clear_tiles()
        # Clear ROI
        if self.roi_manager:
            self.roi_manager.common_roi_rect = None

    def _rebuild_tiles(self):
        """Rebuild tiles based on current selection."""
        self.tile_manager.rebuild_tiles(
            self.all_images,
            self.selected_indices,
            self.grid_size,
            self,
            TileWidget,
            self.set_active_tile,
            self._on_tile_roi_changed,
            self._on_mouse_coords_changed,
            self._on_scroll,
        )

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
        self._initialize_managers()

    def _on_scroll(self, source_index: int, direction: str, value: int, signal_name: str):
        """Handle scroll events."""
        if self.scroll_manager:
            self.scroll_manager.sync_scroll(source_index, direction, value, self.zoom_manager.get_scale())

    def _on_hover_info(self, tile_idx: int, ix: int, iy: int, value_text: str):
        """On hover in any tile, update all tiles' pixel value displays and show coordinates in status bar."""
        # Update each tile's pixel value display with value at (ix, iy)
        displayed_image_data = self.tile_manager.get_displayed_image_data()
        tiles = self.tile_manager.get_tiles()

        for i, data in enumerate(displayed_image_data):
            arr = data.get("base_array", data.get("array"))
            if arr is None:
                tiles[i].update_status("")
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
            tiles[i].update_status(txt)

        # Show only coordinates in status bar
        self.mouse_coords_label.setText(f"({ix}, {iy})")

    def _setup_shortcuts(self):
        """Setup keyboard shortcuts with WindowShortcut context to avoid conflicts."""
        # Clear any existing shortcuts
        self.shortcuts.clear()

        # Helper function to create and register shortcuts
        def add_shortcut(key_seq, callback):
            shortcut = QShortcut(QKeySequence(key_seq), self)
            shortcut.setContext(Qt.WindowShortcut)
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)

        # Help
        add_shortcut("F1", self.show_help)

        # Zoom
        add_shortcut("+", lambda: self.adjust_zoom(2.0))
        add_shortcut("-", lambda: self.adjust_zoom(0.5))
        add_shortcut("f", self.toggle_fit_zoom)

        # Gain
        add_shortcut("<", lambda: self.adjust_gain(0.5))
        add_shortcut(">", lambda: self.adjust_gain(2.0))

        # Brightness dialog
        add_shortcut("D", self.show_brightness_dialog)

        # Reset
        add_shortcut("Ctrl+R", self.reset_brightness)

        # ROI operations
        add_shortcut("Ctrl+A", self.select_all_roi)
        add_shortcut("Esc", self.clear_roi)

        # Arrow key scrolling (synchronized)
        add_shortcut("Left", lambda: self._scroll_by_key(-10, 0, False))
        add_shortcut("Right", lambda: self._scroll_by_key(10, 0, False))
        add_shortcut("Up", lambda: self._scroll_by_key(0, -10, False))
        add_shortcut("Down", lambda: self._scroll_by_key(0, 10, False))
        add_shortcut("Shift+Left", lambda: self._scroll_by_key(-50, 0, True))
        add_shortcut("Shift+Right", lambda: self._scroll_by_key(50, 0, True))
        add_shortcut("Shift+Up", lambda: self._scroll_by_key(0, -50, True))
        add_shortcut("Shift+Down", lambda: self._scroll_by_key(0, 50, True))
        add_shortcut("Ctrl+C", self.copy_active_tile_roi)
        add_shortcut("Ctrl+Shift+C", self.copy_all_tiles_roi_as_grid)

        # Tile rotation
        add_shortcut("Tab", self.rotate_tiles_forward)
        add_shortcut("Shift+Tab", self.rotate_tiles_backward)

        # Tile swapping
        add_shortcut("Ctrl+Shift+Right", self.swap_with_next_tile)
        add_shortcut("Ctrl+Shift+Left", self.swap_with_previous_tile)

    def adjust_zoom(self, factor, tile_index=None, mouse_pos=None):
        """Adjust zoom for all tiles.

        Args:
            factor: Zoom factor (2.0 for zoom in, 0.5 for zoom out)
            tile_index: Index of the tile that triggered the zoom (for mouse position)
            mouse_pos: Mouse position in viewport coordinates (for Ctrl+Wheel zoom)
        """
        if not self.zoom_manager or not self.scroll_manager:
            return

        new_scroll_x, new_scroll_y = self.zoom_manager.adjust_zoom(factor, tile_index, mouse_pos)

        # Apply scroll position
        from PySide6.QtWidgets import QApplication

        self.scroll_manager.apply_scroll_position(new_scroll_x, new_scroll_y)
        QApplication.processEvents()

        self.update_status_bar()

    def toggle_fit_zoom(self):
        """Toggle between fit-to-window and original zoom."""
        if not self.zoom_manager or not self.scroll_manager:
            return

        self.zoom_manager.toggle_fit_zoom(
            lambda idx, dir, val: self.scroll_manager.sync_scroll(idx, dir, val, self.zoom_manager.get_scale())
        )
        self.update_status_bar()

    def adjust_gain(self, factor):
        """Adjust gain (all tiles) using binary steps (powers of 2).

        Args:
            factor: Multiplication factor (2.0 for increase, 0.5 for decrease)
        """
        if self.brightness_manager:
            self.brightness_manager.adjust_gain(factor)
            self.update_status_bar()

    def reset_brightness(self):
        """Reset all brightness parameters."""
        if self.brightness_manager:
            self.brightness_manager.reset_brightness()
            self.update_status_bar()

    def refresh_all_tiles(self):
        """Refresh display for all tiles."""
        if self.brightness_manager:
            self.brightness_manager.refresh_all_tiles()

    def refresh_tiles_by_dtype_group(self, dtype_group: str):
        """Refresh tiles of specific dtype group."""
        if self.brightness_manager:
            self.brightness_manager.refresh_tiles_by_dtype_group(dtype_group)

    def show_brightness_dialog(self):
        """Show brightness adjustment dialog."""
        if not self.brightness_manager:
            return

        if self._brightness_dialog is None:
            params = self.brightness_manager.get_brightness_params()
            self._brightness_dialog = TilingBrightnessDialog(self, params["params_by_dtype"], params["gain"])
            self._brightness_dialog.brightness_changed.connect(self.on_brightness_dialog_changed)

        self._brightness_dialog.show()
        self._brightness_dialog.raise_()
        self._brightness_dialog.activateWindow()

    def show_help(self):
        """Show help dialog with keyboard shortcuts."""
        if self._help_dialog is None:
            self._help_dialog = TilingHelpDialog(self)

        self._help_dialog.show()
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()

    def closeEvent(self, event):
        """Handle dialog close event and close child dialogs."""
        # Close child dialogs
        if self._brightness_dialog is not None:
            self._brightness_dialog.close()
            self._brightness_dialog = None
        if self._help_dialog is not None:
            self._help_dialog.close()
            self._help_dialog = None

        # Accept the close event
        super().closeEvent(event)

    def on_brightness_dialog_changed(self, full_params: Dict):
        """Handle brightness change from dialog.

        Args:
            full_params: Dict mapping dtype groups to {gain, offset, saturation}
        """
        if self.brightness_manager:
            self.brightness_manager.on_brightness_dialog_changed(full_params)
            self.update_status_bar()

    def set_active_tile(self, tile_index: int):
        """Set active tile."""
        if self.tile_manager:
            self.tile_manager.set_active_tile(tile_index)

            # Update ROI display
            if self.roi_manager and self.roi_manager.common_roi_rect:
                self.roi_manager.sync_roi_to_all_tiles(self.roi_manager.common_roi_rect)

    def on_tile_roi_changed(self, roi_rect_in_image_coords: QRect):
        """Handle ROI change from a tile."""
        if self.roi_manager:
            self.roi_manager.on_tile_roi_changed(roi_rect_in_image_coords)
            self.update_status_bar()

    def _on_mouse_coords_changed(self, coords):
        """Handle mouse coordinates change from a tile.

        Args:
            coords: Tuple of (ix, iy) or None
        """
        self.current_mouse_coords = coords
        self.update_status_bar()

        if not self.tile_manager:
            return

        tiles = self.tile_manager.get_tiles()

        # Update pixel values for all tiles at the same coordinate
        if coords is not None:
            ix, iy = coords
            for tile in tiles:
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
            for tile in tiles:
                tile.update_status("")

    def _on_tile_roi_changed(self, roi_rect):
        """Handle ROI change signal from tile (list format).

        Args:
            roi_rect: ROI rectangle as list [x, y, w, h] or None
        """
        if self.roi_manager:
            self.roi_manager.on_tile_roi_changed_list(roi_rect)
            self.update_status_bar()

    def sync_scroll(self, source_index: int, direction: str, value: int):
        """Synchronize scrolls based on viewport-centered normalized position.

        Uses (value + pageStep/2) / (maximum + pageStep) to keep visible region aligned
        across different content sizes and viewport dimensions.
        """
        if self.scroll_manager:
            self.scroll_manager.sync_scroll(
                source_index, direction, value, self.zoom_manager.get_scale() if self.zoom_manager else 1.0
            )

    def sync_roi_to_all_tiles(self, roi_rect: QRect):
        """Sync ROI to all tiles."""
        if self.roi_manager:
            self.roi_manager.sync_roi_to_all_tiles(roi_rect)

    def select_all_roi(self):
        """Select all (full image) for active tile."""
        if self.roi_manager:
            self.roi_manager.select_all_roi()

    def clear_roi(self):
        """Clear ROI from all tiles."""
        if self.roi_manager:
            self.roi_manager.clear_roi()

    def copy_active_tile_roi(self):
        """Copy ROI region from active tile to clipboard."""
        if self.roi_manager:
            self.roi_manager.copy_active_tile_roi()

    def copy_all_tiles_roi_as_grid(self):
        """Copy ROI regions from all tiles arranged in grid layout to clipboard."""
        if self.roi_manager:
            self.roi_manager.copy_all_tiles_roi_as_grid(self.grid_size)

    def rotate_tiles_forward(self):
        """Rotate tiles forward (right rotation)."""
        if self.tile_manager:
            self.tile_manager.rotate_tiles_forward()
            self._update_active_tile_visual()

    def rotate_tiles_backward(self):
        """Rotate tiles backward (left rotation)."""
        if self.tile_manager:
            self.tile_manager.rotate_tiles_backward()
            self._update_active_tile_visual()

    def swap_with_next_tile(self):
        """Swap active tile with next tile."""
        if self.tile_manager:
            self.tile_manager.swap_with_next_tile()

    def swap_with_previous_tile(self):
        """Swap active tile with previous tile."""
        if self.tile_manager:
            self.tile_manager.swap_with_previous_tile()

    def swap_tiles(self, index_a: int, index_b: int):
        """Swap two tiles."""
        if self.tile_manager:
            self.tile_manager.swap_tiles(index_a, index_b)

    def _update_active_tile_visual(self):
        """Update active tile visual state."""
        if not self.tile_manager:
            return

        tiles = self.tile_manager.get_tiles()
        active_idx = self.tile_manager.get_active_tile_index()
        for i, tile in enumerate(tiles):
            tile.set_active(i == active_idx)

        if self.roi_manager and self.roi_manager.common_roi_rect:
            self.roi_manager.sync_roi_to_all_tiles(self.roi_manager.common_roi_rect)

    def update_status_bar(self):
        """Update status bar with current parameters."""
        # Left side: Mouse coordinates
        if self.current_mouse_coords:
            ix, iy = self.current_mouse_coords
            self.mouse_coords_label.setText(f"x={ix} y={iy}")
        else:
            self.mouse_coords_label.setText("")

        # Left side: ROI info
        if self.roi_manager:
            roi_text = self.roi_manager.get_roi_status()
            self.roi_info_label.setText(roi_text)
        else:
            self.roi_info_label.setText("")

        # Right side: Brightness parameters
        if self.brightness_manager:
            brightness_text = self.brightness_manager.get_brightness_status()
            self.brightness_label.setText(brightness_text)
        else:
            self.brightness_label.setText("")

        # Right side: Scale
        if self.zoom_manager:
            scale = self.zoom_manager.get_scale()
            self.scale_label.setText(f" | Scale: {scale:.2f}x")
        else:
            self.scale_label.setText("")

    def _scroll_by_key(self, dx: int, dy: int, is_shift: bool):
        """Scroll all tiles synchronously by arrow keys.

        Args:
            dx: Horizontal scroll delta (positive = right)
            dy: Vertical scroll delta (positive = down)
            is_shift: Whether Shift modifier is pressed
        """
        if self.scroll_manager and self.tile_manager:
            active_idx = self.tile_manager.get_active_tile_index()
            self.scroll_manager.scroll_by_key(active_idx, dx, dy)
