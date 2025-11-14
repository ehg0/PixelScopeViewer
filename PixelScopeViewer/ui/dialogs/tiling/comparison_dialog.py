"""Tiling comparison analysis dialog for comparing multiple tiles.

This module provides a dialog for comparing all tiles side-by-side with:
- Overlay histograms (all tiles on one graph)
- Overlay profiles (all tiles on one graph)
- Metadata comparison table
"""

from typing import List, Dict, Optional, Tuple
import numpy as np

from PySide6.QtWidgets import QDialog, QVBoxLayout, QTabWidget, QMessageBox
from PySide6.QtCore import QRect

from ..analysis.dialog import AnalysisDialog
from PixelScopeViewer.core.image_io import get_image_metadata


class TilingComparisonDialog(AnalysisDialog):
    """Dialog for comparing all tiles with overlay plots.

    Extends AnalysisDialog to handle multiple tiles instead of single image.
    Data is aggregated from all tiles and displayed with different colors.

    Args:
        parent: Parent TilingComparisonDialog widget
        tiles_data: List of dicts with keys: 'array', 'rect', 'path', 'index', 'color'
    """

    def __init__(self, parent=None, tiles_data: Optional[List[Dict]] = None):
        """Initialize comparison dialog.

        Args:
            parent: Parent widget (TilingComparisonDialog)
            tiles_data: List of tile data dicts with:
                - 'array': numpy array of tile image
                - 'rect': QRect of ROI (or None)
                - 'path': file path
                - 'index': tile index
                - 'color': (r, g, b) tuple for plotting
        """
        # Store tiles data before calling parent init
        self.tiles_data = tiles_data or []

        # Initialize with first tile's data (or None if no tiles)
        # Pass image_rect=None to parent to prevent ROI application during parent's __init__
        # Our update_contents() will handle ROI application properly
        if self.tiles_data:
            first_tile = self.tiles_data[0]
            image_array = first_tile["array"]
            image_path = first_tile.get("path")
        else:
            image_array = None
            image_path = None

        # Call parent constructor with image_rect=None
        super().__init__(parent=parent, image_array=image_array, image_rect=None, image_path=image_path)

        # Set window title
        self.setWindowTitle("Tiling Comparison")

    def update_tiles_data(self, tiles_data: List[Dict]):
        """Update with new tiles data.

        Args:
            tiles_data: List of tile data dicts
        """
        self.tiles_data = tiles_data

        if self.tiles_data:
            # Update with first tile's data to trigger refresh
            first_tile = self.tiles_data[0]
            self.set_image_and_rect(first_tile["array"], first_tile.get("rect"), first_tile.get("path"))
        else:
            self.set_image_and_rect(None, None, None)

    def _update_metadata(self):
        """Override to show comparison table of all tiles' metadata."""
        if not hasattr(self, "metadata_table"):
            return

        if not self.tiles_data:
            self.meta_tab.update([("Info", "No tiles available")])
            return

        # Collect metadata from all tiles
        all_metadata = []
        for tile_data in self.tiles_data:
            path = tile_data.get("path")
            arr = tile_data.get("array")

            metadata = {}

            if path:
                try:
                    metadata = get_image_metadata(path) or {}
                except Exception:
                    pass

            # Add/Override basic information from array (ensure they are always present)
            if arr is not None:
                h, w = arr.shape[:2]
                metadata["Size"] = f"{w} x {h}"
                if arr.ndim == 3:
                    metadata["Channels"] = arr.shape[2]
                elif arr.ndim == 2:
                    metadata["Channels"] = 1
                metadata["DataType"] = str(arr.dtype)

                # Add FileSize if path exists
                if path:
                    try:
                        from pathlib import Path

                        file_size = Path(path).stat().st_size
                        metadata["FileSize"] = f"{file_size:,} bytes"
                    except Exception:
                        pass

            all_metadata.append({"index": tile_data["index"], "path": path, "metadata": metadata})

        if not all_metadata:
            self.meta_tab.update([("Info", "No metadata available")])
            return

        # Build comparison table
        self._build_comparison_table(all_metadata)

    def _build_comparison_table(self, all_metadata: List[Dict]):
        """Build comparison table from all tiles' metadata.

        Args:
            all_metadata: List of dicts with 'index', 'path', 'metadata'
        """
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtGui import QBrush, QColor
        from pathlib import Path

        # Collect all unique keys
        all_keys = set()
        for tile_meta in all_metadata:
            all_keys.update(tile_meta["metadata"].keys())

        # Sort keys to match main side order: Basic info first, then EXIF tags
        basic_keys = ["Filepath", "Format", "FileSize", "Size", "Channels", "DataType"]
        sorted_keys = [k for k in basic_keys if k in all_keys]
        exif_keys = sorted([k for k in all_keys if k not in basic_keys])
        sorted_keys.extend(exif_keys)

        # Setup table
        num_tiles = len(all_metadata)
        num_rows = len(sorted_keys)

        # Column count: Property + Tile columns
        self.metadata_table.setColumnCount(1 + num_tiles)

        # Set headers
        headers = ["Property"]
        for tile_meta in all_metadata:
            tile_idx = tile_meta["index"] + 1  # Display as 1-indexed
            path = tile_meta["path"]
            if path:
                filename = Path(path).name
                headers.append(f"Tile {tile_idx}\n{filename}")
            else:
                headers.append(f"Tile {tile_idx}\n(no file)")

        self.metadata_table.setHorizontalHeaderLabels(headers)
        self.metadata_table.setRowCount(num_rows)

        # Highlight color for differences
        diff_color = QColor(255, 255, 200)  # Light yellow

        # Fill table
        for row_idx, key in enumerate(sorted_keys):
            # Property column
            prop_item = QTableWidgetItem(key)
            self.metadata_table.setItem(row_idx, 0, prop_item)

            # Collect values for this property from all tiles
            values = []
            for tile_meta in all_metadata:
                value = tile_meta["metadata"].get(key, "")
                values.append(str(value) if value else "")

            # Check if all values are the same
            unique_values = set(v for v in values if v)  # Exclude empty strings
            has_difference = len(unique_values) > 1

            # Exclude FileSize, Filepath from highlighting (these are expected to differ)
            exclude_from_highlight = {"FileSize", "Filepath"}
            should_highlight = has_difference and key not in exclude_from_highlight

            # Fill tile columns
            for col_idx, value in enumerate(values):
                value_item = QTableWidgetItem(value)

                # Highlight if there's a difference (but not for excluded keys)
                if should_highlight and value:
                    value_item.setBackground(QBrush(diff_color))

                self.metadata_table.setItem(row_idx, col_idx + 1, value_item)

        # Adjust column widths
        header = self.metadata_table.horizontalHeader()
        from PySide6.QtWidgets import QHeaderView

        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Property column
        for i in range(1, 1 + num_tiles):
            header.setSectionResizeMode(i, QHeaderView.Stretch)  # Tile columns

    def update_contents(self):
        """Override to aggregate data from all tiles and overlay plots."""
        # Always update metadata first
        self._update_metadata()

        if not self.tiles_data:
            return

        # For Phase 2 initial implementation: show first tile's data only
        # TODO: Implement full overlay in future iteration
        first_tile = self.tiles_data[0]
        arr = first_tile["array"]

        if arr is None:
            return

        # Apply ROI if present
        roi_rect = first_tile.get("rect")
        if roi_rect is not None:
            x, y, w, h = (
                int(roi_rect.x()),
                int(roi_rect.y()),
                int(roi_rect.width()),
                int(roi_rect.height()),
            )
            arr = arr[y : y + h, x : x + w]

        # Check for empty array after ROI application
        if arr.size == 0:
            return

        # Set the array (already ROI-applied) and set rect to None
        # IMPORTANT: Set image_rect=None because arr is already ROI-applied
        # If we set image_rect, parent's update_contents will apply ROI again, causing out-of-bounds error
        self.image_array = arr
        self.image_rect = None  # Already applied ROI to arr, so don't apply again

        # Call parent implementation for histogram and profile
        # This will use the first tile's data for now
        super().update_contents()
