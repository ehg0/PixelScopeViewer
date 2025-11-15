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

        # Prepare initial single-image parameters for base dialog.
        # NOTE: overlay_channel_visibility must exist BEFORE calling super().__init__
        # because base __init__ invokes update_contents(), which references it.
        self.overlay_channel_visibility: dict[int, list[bool]] = {}

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

        # ---- Overlay color palette (Tableau 20) & mapping (must exist before super().__init__) ----
        self.TABLEAU20: list[tuple[int, int, int]] = [
            (31, 119, 180),
            (174, 199, 232),
            (255, 127, 14),
            (255, 187, 120),
            (44, 160, 44),
            (152, 223, 138),
            (214, 39, 40),
            (255, 152, 150),
            (148, 103, 189),
            (197, 176, 213),
            (140, 86, 75),
            (196, 156, 148),
            (227, 119, 194),
            (247, 182, 210),
            (127, 127, 127),
            (199, 199, 199),
            (188, 189, 34),
            (219, 219, 141),
            (23, 190, 207),
            (158, 218, 229),
        ]
        self.overlay_color_map: dict[str, tuple[int, int, int]] = {}
        self.hist_plot_items: dict[str, object] = {}
        self.profile_plot_items: dict[str, object] = {}

        # Call parent constructor with image_rect=None (will trigger update_contents which needs above attrs)
        super().__init__(parent=parent, image_array=image_array, image_rect=None, image_path=image_path)

        # Set window title
        self.setWindowTitle("Tiling Comparison")

        # Hook channel configure buttons from base tabs (if available)
        try:
            if hasattr(self, "hist_channels_btn"):
                # Disconnect base handler if connected, then connect overlay config
                try:
                    self.hist_channels_btn.clicked.disconnect()
                except Exception:
                    pass
                self.hist_channels_btn.clicked.connect(self._open_overlay_channel_config)
            if hasattr(self, "prof_channels_btn"):
                try:
                    self.prof_channels_btn.clicked.disconnect()
                except Exception:
                    pass
                self.prof_channels_btn.clicked.connect(self._open_overlay_channel_config)
        except Exception:
            pass

        # (Palette & mapping already initialized before super().__init__)

    # ---- Color & highlight helpers ----
    def _assign_overlay_colors(self, labels: list[str]):
        # Deterministic mapping: parse 'Tile {n} Ck' or 'Tile {n} I'
        # Compute palette index from (tile_number, channel_index)
        for lbl in labels:
            if lbl in self.overlay_color_map:
                continue
            parts = lbl.split()
            tile_num = 1
            ch_index = 0
            try:
                # Expected parts: ['Tile', 'N', 'Ck'/'I']
                # Some labels may be 'Tile N Ck'
                if len(parts) >= 3 and parts[0] == "Tile":
                    tile_num = int(parts[1])
                    ch_code = parts[2]
                    if ch_code.startswith("C"):
                        ch_index = int(ch_code[1:])
                    else:
                        ch_index = 0  # 'I'
                else:
                    # Fallback: search for numeric tile
                    for p in parts:
                        if p.isdigit():
                            tile_num = int(p)
                            break
                    for p in parts:
                        if p.startswith("C") and p[1:].isdigit():
                            ch_index = int(p[1:])
                            break
            except Exception:
                tile_num = 1
                ch_index = 0
            # Generate stable index (spread channels within tile)
            idx = ((tile_num - 1) * 8 + ch_index) % len(self.TABLEAU20)
            self.overlay_color_map[lbl] = self.TABLEAU20[idx]
        return {lbl: self.overlay_color_map[lbl] for lbl in labels}

    def _make_pen(self, rgb: tuple[int, int, int], *, width: int = 2, alpha: int = 255):
        try:
            import pyqtgraph as pg
        except ImportError:
            return None
        r, g, b = rgb
        return pg.mkPen(color=(r, g, b, alpha), width=width)

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

                # Note: FileSize is provided by get_image_metadata for consistency with main viewer

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

            # Highlight any difference (no exceptions)
            should_highlight = has_difference

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

        # Import necessary functions for histogram and profile computation
        from ..analysis.core.compute import (
            determine_hist_bins,
            histogram_series,
            histogram_stats,
            profile_series,
            get_profile_offset,
        )
        import numpy as np

        try:
            import pyqtgraph as pg

            PYQTGRAPH_AVAILABLE = True
        except ImportError:
            PYQTGRAPH_AVAILABLE = False

        if not PYQTGRAPH_AVAILABLE:
            return

        # Collect valid tile arrays after ROI application
        valid_tiles = []
        for tile_data in self.tiles_data:
            arr = tile_data["array"]
            if arr is None:
                continue

            # Apply ROI if present
            roi_rect = tile_data.get("rect")
            if roi_rect is not None:
                x, y, w, h = (
                    int(roi_rect.x()),
                    int(roi_rect.y()),
                    int(roi_rect.width()),
                    int(roi_rect.height()),
                )
                arr = arr[y : y + h, x : x + w]

            # Skip empty arrays
            if arr.size == 0:
                continue

            valid_tiles.append(
                {
                    "array": arr,
                    "index": tile_data["index"],
                    "color": tile_data["color"],
                    "rect": roi_rect,
                }
            )

        if not valid_tiles:
            return

        # Use first tile's array for parent's image_array (for metadata, etc.)
        self.image_array = valid_tiles[0]["array"]
        self.image_rect = None  # Already ROI-applied

        # Ensure channel_checks are initialized
        first_arr = valid_tiles[0]["array"]
        if first_arr.ndim == 3 and first_arr.shape[2] > 1:
            nch = first_arr.shape[2]
            if not self.channel_checks:
                self.channel_checks = [True] * nch
            elif len(self.channel_checks) < nch:
                self.channel_checks.extend([True] * (nch - len(self.channel_checks)))

        # Initialize / ensure overlay channel visibilities
        self._ensure_overlay_channel_visibility(valid_tiles)

        # Histogram & Profile overlays
        self._update_histogram_overlay(valid_tiles)
        self._update_profile_overlay(valid_tiles)

    def _update_histogram_overlay(self, valid_tiles):
        """Update histogram tab with overlaid data from all tiles."""
        from ..analysis.core.compute import determine_hist_bins, histogram_series, histogram_stats
        import numpy as np

        try:
            import pyqtgraph as pg
        except ImportError:
            return

        # Determine global histogram bin edges (to unify xs across tiles)
        if not valid_tiles:
            return
        first_arr = valid_tiles[0]["array"]
        is_float = np.issubdtype(first_arr.dtype, np.floating)
        # Global min/max across all tiles
        global_min = min(arr_tile["array"].min() for arr_tile in valid_tiles)
        global_max = max(arr_tile["array"].max() for arr_tile in valid_tiles)
        if is_float:
            bin_count = 256
        else:
            bin_count = max(1, int(global_max - global_min) + 1)
        # Construct common bin edges
        common_edges = np.linspace(global_min, global_max, bin_count + 1)

        # Collect all histogram data with unified bins
        all_hist_series = {}  # tile_idx -> {label -> (xs, ys)}
        all_stats = []  # List of stats dicts with tile info (filtered by visibility)

        for tile in valid_tiles:
            arr = tile["array"]
            tile_idx = tile["index"]
            visibility = self.overlay_channel_visibility.get(tile_idx)

            hist_series = histogram_series(arr, bins=common_edges)
            stats = histogram_stats(arr, self.channel_checks)

            tile_hist_series = {}
            for label, (xs, ys) in hist_series.items():
                # Remap grayscale 'I' to unified channel code 'C0'
                channel_code = "C0" if label == "I" else label
                ch_visible = True
                if visibility is not None:
                    if label.startswith("C"):
                        try:
                            cindex = int(label[1:])
                            if cindex < len(visibility):
                                ch_visible = visibility[cindex]
                        except Exception:
                            ch_visible = True
                    elif label == "I":
                        if len(visibility) > 0:
                            ch_visible = visibility[0]
                if ch_visible:
                    new_label = f"Tile {tile_idx + 1} {channel_code}"
                    tile_hist_series[new_label] = (xs, ys)
            all_hist_series[tile_idx] = tile_hist_series

            # Stats filtered by visibility
            for stat in stats:
                stat_ch_index = 0
                try:
                    stat_ch_index = int(stat["ch"])  # grayscale '0' or color index
                except Exception:
                    stat_ch_index = 0
                stat_visible = True
                if visibility is not None and stat_ch_index < len(visibility):
                    stat_visible = visibility[stat_ch_index]
                if stat_visible:
                    stat_copy = stat.copy()
                    # Unified channel label format always C{index}; grayscale->C0
                    stat_label = f"C{stat_ch_index}"
                    curve_label = f"Tile {tile_idx + 1} {stat_label}"
                    stat_copy["ch"] = f"T{tile_idx + 1}_C{stat_ch_index}"
                    stat_copy["curve_label"] = curve_label
                    all_stats.append(stat_copy)

        # Merge all series for plotting
        merged_series = {}
        for tile_idx, series in all_hist_series.items():
            for label, data in series.items():
                merged_series[label] = data

        # Assign colors from palette (stable)
        ordered_labels = list(merged_series.keys())
        palette_map = self._assign_overlay_colors(ordered_labels)

        # Update histogram tab with custom colors
        apply_log = self.plot_settings.get("hist", {}).get("log", False)

        if self.hist_tab.hist_widget:
            self.hist_tab.hist_widget.clear()
            self.hist_plot_items.clear()
            if merged_series:
                for label, (xs, ys) in merged_series.items():
                    rgb = palette_map.get(label, (127, 127, 127))
                    yplot = ys
                    if apply_log:
                        with np.errstate(divide="ignore"):
                            yplot = np.log10(ys.astype(float) + 1.0)
                    pen = self._make_pen(rgb, width=2, alpha=255)
                    item = self.hist_tab.hist_widget.plot(xs, yplot, pen=pen, name=label)
                    self.hist_plot_items[label] = item
                self.hist_tab.hist_widget.setTitle("Histogram Overlay (All Tiles)", color="#2c3e50", size="12pt")
            else:
                self.hist_tab.hist_widget.setTitle(
                    "Histogram Overlay (No channels visible)", color="#7f8c8d", size="11pt"
                )

        # Update stats table
        self.hist_tab._populate_stats_table(all_stats)

        # Store for copy (only visible series)
        self.last_hist_data = merged_series

    def _update_profile_overlay(self, valid_tiles):
        """Update profile tab with overlaid data from all tiles."""
        from ..analysis.core.compute import profile_series, get_profile_offset
        import numpy as np

        try:
            import pyqtgraph as pg
        except ImportError:
            return

        # Collect all profile data
        all_prof_series = {}  # tile_idx -> {label -> (xs, ys)}
        all_profile_stats = []  # stats rows

        for tile in valid_tiles:
            arr = tile["array"]
            tile_idx = tile["index"]
            roi_rect = tile.get("rect")
            visibility = self.overlay_channel_visibility.get(tile_idx)

            pseries = profile_series(arr, orientation=self.profile_orientation)

            tile_prof_series = {}
            for label, prof in pseries.items():
                if self.x_mode == "absolute" and roi_rect is not None:
                    offset = get_profile_offset(roi_rect, self.profile_orientation)
                    xs = np.arange(prof.size) + offset
                else:
                    xs = np.arange(prof.size)

                ch_visible = True
                if visibility is not None:
                    if label.startswith("C"):
                        try:
                            cindex = int(label[1:])
                            if cindex < len(visibility):
                                ch_visible = visibility[cindex]
                        except Exception:
                            ch_visible = True
                    elif label == "I":
                        if len(visibility) > 0:
                            ch_visible = visibility[0]

                if ch_visible:
                    channel_code = "C0" if label == "I" else label
                    new_label = f"Tile {tile_idx + 1} {channel_code}"
                    tile_prof_series[new_label] = (xs, prof)
                    is_int = np.issubdtype(prof.dtype, np.integer)
                    all_profile_stats.append(
                        {
                            "ch": f"T{tile_idx + 1}_C{0 if label=='I' else int(label[1:])}",
                            "mean": float(prof.mean()) if prof.size else 0.0,
                            "std": float(prof.std()) if prof.size else 0.0,
                            "median": float(np.median(prof)) if prof.size else 0.0,
                            "min": float(prof.min()) if prof.size else 0.0,
                            "max": float(prof.max()) if prof.size else 0.0,
                            "is_int": bool(is_int),
                            "curve_label": new_label,
                        }
                    )

            all_prof_series[tile_idx] = tile_prof_series

        # Merge all series for plotting
        merged_series = {}
        for tile_idx, series in all_prof_series.items():
            for label, data in series.items():
                merged_series[label] = data

        ordered_prof_labels = list(merged_series.keys())
        prof_palette_map = self._assign_overlay_colors(ordered_prof_labels)

        # Update profile tab with custom colors
        if hasattr(self, "prof_widget") and self.prof_widget:
            self.prof_widget.clear()
            self.profile_plot_items.clear()
            orientation_text = "Horizontal" if self.profile_orientation == "h" else "Vertical"
            if merged_series:
                for label, (xs, ys) in merged_series.items():
                    rgb = prof_palette_map.get(label, (127, 127, 127))
                    pen = self._make_pen(rgb, width=2, alpha=255)
                    item = self.prof_widget.plot(xs, ys, pen=pen, name=label)
                    self.profile_plot_items[label] = item
                self.prof_widget.setTitle(
                    f"{orientation_text} Profile Overlay (All Tiles)", color="#2c3e50", size="12pt"
                )
            else:
                self.prof_widget.setTitle(
                    f"{orientation_text} Profile Overlay (No channels visible)", color="#7f8c8d", size="11pt"
                )

        # Update profile stats table
        if hasattr(self, "profile_tab"):
            self.profile_tab._populate_stats_table(all_profile_stats)

        # Store for copy
        self.last_profile_data = merged_series

    # ---- Overlay Channel Visibility Helpers ----
    def _ensure_overlay_channel_visibility(self, valid_tiles):
        for tile in valid_tiles:
            idx = tile["index"]
            arr = tile["array"]
            if idx not in self.overlay_channel_visibility:
                if arr.ndim == 3:
                    self.overlay_channel_visibility[idx] = [True] * arr.shape[2]
                else:
                    self.overlay_channel_visibility[idx] = [True]

    def _open_overlay_channel_config(self):
        from PySide6.QtWidgets import (
            QDialog,
            QVBoxLayout,
            QHBoxLayout,
            QCheckBox,
            QLabel,
            QPushButton,
            QWidget,
        )
        from PySide6.QtGui import QPixmap, QColor
        from PySide6.QtCore import Qt

        dlg = QDialog(self)
        dlg.setWindowTitle("Overlay Channel Visibility")
        root_layout = QVBoxLayout(dlg)

        checkbox_meta = []  # (tile_idx, ch_idx, checkbox)
        for tile_idx, vis_list in sorted(self.overlay_channel_visibility.items()):
            group = QWidget()
            gl = QVBoxLayout(group)
            gl.setContentsMargins(0, 0, 0, 0)
            gl.addWidget(QLabel(f"Tile {tile_idx + 1}"))
            for ch_idx, enabled in enumerate(vis_list):
                # Build curve label used for color mapping
                if len(vis_list) > 1:
                    channel_code = f"C{ch_idx}"
                    label = f"{channel_code}"
                else:
                    channel_code = "I"
                    label = "Intensity"
                curve_label = f"Tile {tile_idx + 1} {channel_code}"
                # Ensure color assignment exists
                self._assign_overlay_colors([curve_label])
                rgb = self.overlay_color_map.get(curve_label, (127, 127, 127))
                cb = QCheckBox(label)
                # Add color swatch icon
                pix = QPixmap(14, 14)
                pix.fill(QColor(*rgb))
                cb.setIcon(pix)
                cb.setIconSize(pix.size())
                cb.setChecked(enabled)
                # Live update on toggle
                cb.toggled.connect(
                    lambda checked, t=tile_idx, c=ch_idx: self._on_overlay_channel_toggled(t, c, checked)
                )
                gl.addWidget(cb)
                checkbox_meta.append((tile_idx, ch_idx, cb))
            root_layout.addWidget(group)

        # Select / Deselect All buttons
        btn_row = QHBoxLayout()
        select_all_btn = QPushButton("全選択")
        clear_all_btn = QPushButton("全解除")
        btn_row.addWidget(select_all_btn)
        btn_row.addWidget(clear_all_btn)
        root_layout.addLayout(btn_row)

        def _apply_all(value: bool):
            for tile_idx, ch_idx, cb in checkbox_meta:
                if cb.isChecked() != value:
                    cb.setChecked(value)  # triggers live update

        select_all_btn.clicked.connect(lambda: _apply_all(True))
        clear_all_btn.clicked.connect(lambda: _apply_all(False))

        dlg.setModal(False)
        dlg.show()

    def _on_overlay_channel_toggled(self, tile_idx: int, ch_idx: int, checked: bool):
        vis = self.overlay_channel_visibility.get(tile_idx)
        if not vis or ch_idx >= len(vis):
            return
        vis[ch_idx] = bool(checked)
        # Incremental update: re-render overlays (metadata unaffected)
        try:
            self._update_histogram_overlay(self._collect_valid_tiles())
            self._update_profile_overlay(self._collect_valid_tiles())
        except Exception:
            # Fallback to full refresh if something goes wrong
            self.update_contents()

    def _collect_valid_tiles(self):
        valid = []
        for tile_data in self.tiles_data:
            arr = tile_data["array"]
            if arr is None:
                continue
            roi_rect = tile_data.get("rect")
            if roi_rect is not None:
                x, y, w, h = (
                    int(roi_rect.x()),
                    int(roi_rect.y()),
                    int(roi_rect.width()),
                    int(roi_rect.height()),
                )
                arr = arr[y : y + h, x : x + w]
            if arr is not None and arr.size > 0:
                valid.append({"array": arr, "index": tile_data["index"], "color": tile_data["color"], "rect": roi_rect})
        return valid
