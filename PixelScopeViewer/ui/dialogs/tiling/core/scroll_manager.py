"""Scroll synchronization for tiling comparison."""

from typing import List
from PySide6.QtCore import QCoreApplication


class ScrollManager:
    """Manages scroll synchronization across tiles."""

    def __init__(self, tiles: List):
        """Initialize scroll manager.

        Args:
            tiles: List of TileWidget instances
        """
        self.tiles = tiles
        self._syncing_scroll = False

    def sync_scroll(self, source_index: int, direction: str, value: int, scale: float):
        """Synchronize scrolls based on viewport-centered normalized position.

        Uses (value + pageStep/2) / (maximum + pageStep) to keep visible region aligned
        across different content sizes and viewport dimensions.

        Args:
            source_index: Index of the source tile
            direction: 'h' for horizontal, 'v' for vertical
            value: Scroll value from the source tile
            scale: Current zoom scale
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
                QCoreApplication.processEvents()

        finally:
            self._syncing_scroll = False

    def apply_scroll_position(self, new_scroll_x: float, new_scroll_y: float):
        """Apply scroll position to all tiles.

        Args:
            new_scroll_x: New horizontal scroll position
            new_scroll_y: New vertical scroll position
        """
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

    def scroll_by_key(self, active_tile_index: int, dx: int, dy: int):
        """Scroll all tiles synchronously by arrow keys.

        Args:
            active_tile_index: Index of the active tile
            dx: Horizontal scroll delta (positive = right)
            dy: Vertical scroll delta (positive = down)

        Returns:
            True if scrolling was performed, False otherwise
        """
        if not self.tiles or active_tile_index >= len(self.tiles):
            return False

        active_tile = self.tiles[active_tile_index]
        scroll_area = active_tile.scroll_area

        # Apply horizontal scroll
        if dx != 0:
            hsb = scroll_area.horizontalScrollBar()
            if hsb:
                new_val = hsb.value() + dx
                new_val = max(hsb.minimum(), min(hsb.maximum(), new_val))
                hsb.setValue(new_val)
                self.sync_scroll(active_tile_index, "h", new_val, 1.0)

        # Apply vertical scroll
        if dy != 0:
            vsb = scroll_area.verticalScrollBar()
            if vsb:
                new_val = vsb.value() + dy
                new_val = max(vsb.minimum(), min(vsb.maximum(), new_val))
                vsb.setValue(new_val)
                self.sync_scroll(active_tile_index, "v", new_val, 1.0)

        return True

    def is_syncing(self) -> bool:
        """Check if currently syncing scroll."""
        return self._syncing_scroll
