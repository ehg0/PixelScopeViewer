"""Tile management for tiling comparison."""

from typing import List, Dict, Tuple
from PySide6.QtWidgets import QGridLayout

from .utils import determine_dtype_group


class TileManager:
    """Manages tile widgets and their organization."""

    def __init__(self, grid_layout: QGridLayout):
        """Initialize tile manager.

        Args:
            grid_layout: QGridLayout to place tiles in
        """
        self.grid_layout = grid_layout
        self.tiles: List = []
        self.tile_dtype_groups: List[str] = []
        self.displayed_image_data: List[Dict] = []
        self.active_tile_index = 0

    def clear_tiles(self):
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

    def rebuild_tiles(
        self,
        all_images: List[Dict],
        selected_indices: List[int],
        grid_size: Tuple[int, int],
        parent_dialog,
        tile_widget_class,
        on_activated_func,
        on_roi_changed_func,
        on_mouse_coords_changed_func,
        on_scroll_func,
    ):
        """Rebuild tiles based on current selection.

        Args:
            all_images: All available images
            selected_indices: Indices of selected images
            grid_size: Tuple of (rows, cols)
            parent_dialog: Parent dialog
            tile_widget_class: TileWidget class
            on_activated_func: Callback when tile is activated
            on_roi_changed_func: Callback when ROI changes
            on_mouse_coords_changed_func: Callback when mouse coordinates change
            on_scroll_func: Callback when scrolling occurs
        """
        rows, cols = grid_size

        # Create tiles
        for i, img_idx in enumerate(selected_indices):
            if img_idx >= len(all_images):
                continue

            image_data = all_images[img_idx].copy()
            self.displayed_image_data.append(image_data)

            # Determine dtype group
            arr = image_data.get("base_array", image_data.get("array"))
            dtype_group = determine_dtype_group(arr)
            self.tile_dtype_groups.append(dtype_group)

            # Create tile widget
            tile = tile_widget_class(image_data, parent_dialog, i)
            tile.activated.connect(lambda idx=i: on_activated_func(idx))
            tile.roi_changed.connect(on_roi_changed_func)
            tile.mouse_coords_changed.connect(on_mouse_coords_changed_func)

            self.tiles.append(tile)

            # Add to grid
            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(tile, row, col)

            # Initial display will be triggered after managers are initialized
            # Connect scrollbars for sync - use ONLY sliderMoved to avoid signal conflicts
            if tile.scroll_area.horizontalScrollBar():
                hsb = tile.scroll_area.horizontalScrollBar()
                # sliderMoved: user dragging scrollbar thumb
                hsb.sliderMoved.connect(lambda val, idx=i: on_scroll_func(idx, "h", val, "sliderMoved"))
            if tile.scroll_area.verticalScrollBar():
                vsb = tile.scroll_area.verticalScrollBar()
                # sliderMoved: user dragging scrollbar thumb
                vsb.sliderMoved.connect(lambda val, idx=i: on_scroll_func(idx, "v", val, "sliderMoved"))

    def set_active_tile(self, tile_index: int):
        """Set active tile.

        Args:
            tile_index: Index of tile to activate
        """
        if tile_index < 0 or tile_index >= len(self.tiles):
            return

        # Deactivate previous
        if 0 <= self.active_tile_index < len(self.tiles):
            self.tiles[self.active_tile_index].set_active(False)

        # Activate new
        self.active_tile_index = tile_index
        self.tiles[tile_index].set_active(True)

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

    def swap_tiles(self, index_a: int, index_b: int):
        """Swap two tiles.

        Args:
            index_a: First tile index
            index_b: Second tile index
        """
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

    def _update_active_tile_visual(self):
        """Update active tile visual state."""
        for i, tile in enumerate(self.tiles):
            tile.set_active(i == self.active_tile_index)

    def get_active_tile_index(self) -> int:
        """Get the active tile index."""
        return self.active_tile_index

    def get_tiles(self) -> List:
        """Get list of tiles."""
        return self.tiles

    def get_tile_dtype_groups(self) -> List[str]:
        """Get list of tile dtype groups."""
        return self.tile_dtype_groups

    def get_displayed_image_data(self) -> List[Dict]:
        """Get list of displayed image data."""
        return self.displayed_image_data
