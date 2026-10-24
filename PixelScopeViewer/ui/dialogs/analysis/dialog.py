"""Analysis dialog with tabbed interface for image analysis.

This module provides the main AnalysisDialog which displays:
- Histogram tab: Intensity histogram with customizable channels and statistical information
- Profile tab: Line profile (horizontal/vertical/diagonal) with absolute/relative modes and statistical information
- Metadata tab: Image metadata in table format with EXIF information

The dialog supports pyqtgraph-based interactive plots with right-click
context menus for plot configuration. If pyqtgraph is not available, the
histogram and profile tabs will show empty placeholders.

Statistical information displayed includes:
- Mean: Average intensity value
- Std: Standard deviation of intensity values
- Min: Minimum intensity value
- Max: Maximum intensity value
- Median: Median intensity value

Dependencies:
    - pyqtgraph (optional): For fast histogram and profile plotting
    - numpy: For data processing
    - exifread: For comprehensive EXIF metadata reading
"""

import contextlib

import numpy as np
from PySide6.QtCore import QEvent, QRect, Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ....core.image_io import get_image_metadata

try:
    import pyqtgraph as pg
    from pyqtgraph import PlotWidget

    PYQTGRAPH_AVAILABLE = True

except ImportError:
    pg = None
    PlotWidget = None
    PYQTGRAPH_AVAILABLE = False

from ...utils.color_utils import get_default_channel_colors
from .core import (
    calc_stats,
    compute_profile_1d,
    determine_hist_bins,
    ecdf_series,
    get_profile_offset,
    histogram_series,
    histogram_stats,
    profile_series,
    profile_stats,
)
from .exporting import series_to_csv
from .plotting import apply_plot_settings as pg_apply_plot_settings
from .plotting import connect_plot_controls as pg_connect_plot_controls
from .plotting import save_viewbox_state as pg_save_viewbox_state
from .tabs.histogram_tab import HistogramTab
from .tabs.metadata_tab import MetadataTab
from .tabs.profile_tab import ProfileTab


class AnalysisDialog(QDialog):
    """Main analysis dialog with tabbed interface for Metadata, Histogram, and Profile.

    This dialog provides three tabs for analyzing image selections:

    1. Metadata Tab:
       - Displays comprehensive image metadata including EXIF information
       - Copyable table format

    2. Histogram Tab:
       - Shows intensity distribution across all channels
       - Statistical information: mean, std, min, max, median for visible channels
       - Customizable via "Channels..." button
       - "Copy data" exports histogram as CSV to clipboard

    4. Profile Tab:
       - Shows averaged intensity profile along a direction
       - Statistical information: mean, std, min, max, median for visible channels
       - Customizable via "Channels..." button
       - "Copy data" exports profile as CSV to clipboard

    The dialog is modeless and updates automatically when the parent
    viewer's selection changes (via set_image_and_rect).

    Args:
        parent: Parent widget (typically ImageViewer)
        image_array: NumPy array of the image or selection
        image_rect: QRect defining the selection in image coordinates

    Usage:
        dlg = AnalysisDialog(parent, image_array=arr, image_rect=rect)
        dlg.show()  # Modeless

        # Update when selection changes:
        dlg.set_image_and_rect(new_array, new_rect)

    Note:
        Requires pyqtgraph for histogram and profile plots. If pyqtgraph
        is not available, those tabs will be empty.
    """

    # Persist window geometry across openings so it doesn't jump based on cursor/OS heuristics
    _saved_geometry = None
    # Store position before minimize to restore after showNormal()
    _position_before_minimize = None

    def __init__(
        self,
        parent=None,
        image_array: np.ndarray | None = None,
        image_rect: QRect | None = None,
        image_path: str | None = None,
    ):
        super().__init__(parent)
        self.viewer = parent
        self.update_window_title()

        # 親側でROIが切り直されたときにタイトルを自動更新する設定
        if self.viewer and hasattr(self.viewer, "roi_changed"):
            self.viewer.roi_changed.connect(self.update_window_title)

        self.resize(900, 600)

        # Set window flags to allow minimizing and prevent staying on top
        flags = Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.image_array = image_array
        self.image_rect = image_rect
        self.image_path = image_path

        # state
        self.profile_orientation = "h"  # "h", "v"
        self.x_mode = "relative"  # "relative", "absolute"
        self.profile_compute_method = "mean"  # "mean", "std", "max", "min", "p2p", "median"
        self.hist_config_mode = "Histogram"  # "Histogram", "ECDF"
        self.hist_yscale = "linear"
        self.channel_checks: list[bool] = []
        self.spinbox_value: float = 1.0
        self.hist_chart_kind = "Line"
        self.spinbox_bar_alpha_value: int = 120

        self.last_hist_data = {}
        self.last_profile_data = {}

        # Channel color mapping for color swatches (label -> rgb tuple)
        self.channel_color_map: dict[str, tuple[int, int, int]] = {}

        # Persisted plot settings for histogram/profile (kept across image switches)
        # keys: 'hist' and 'prof' with values for grid/log/autorange
        self.plot_settings = {
            "hist": {"grid": True, "log": False, "auto_range": True},
            "prof": {"grid": True, "auto_range": True},
        }

        self._build_ui()

        # Restore last window geometry if available to avoid cursor-dependent positioning
        try:
            if AnalysisDialog._saved_geometry:
                self.restoreGeometry(AnalysisDialog._saved_geometry)
        except Exception:
            pass

        if self.image_array is not None:
            self.update_contents()

    def _build_ui(self):
        main = QVBoxLayout(self)
        self.tabs = QTabWidget()
        main.addWidget(self.tabs)

        # Metadata tab (modular)
        self.meta_tab = MetadataTab(self)
        # Map child widgets to keep rest of code unchanged
        self.metadata_table = self.meta_tab.metadata_table
        self.metadata_copy_btn = self.meta_tab.copy_btn
        self.metadata_copy_btn.clicked.connect(self.copy_metadata_to_clipboard)
        self.tabs.addTab(self.meta_tab, "Metadata")

        # Profile tab (modular)
        self.profile_tab = ProfileTab(
            PYQTGRAPH_AVAILABLE,
            on_save_viewbox_state=lambda vb: self._save_viewbox_state(vb, "prof"),
            on_connect_plot_controls=lambda plot_item: self._connect_plotitem_controls(plot_item, "prof"),
            on_channel_changed=lambda checks: self._on_channel_changed(checks),
            parent=self,
        )
        self.prof_widget = self.profile_tab.prof_widget
        self.prof_stats_table = self.profile_tab.prof_stats_table
        self.prof_orientation_btn = self.profile_tab.orientation_btn
        self.prof_xmode_btn = self.profile_tab.xmode_btn
        self.prof_compute_method_combo = self.profile_tab.compute_method_combo
        self.prof_copy_btn = self.profile_tab.copy_btn
        self.prof_copy_stats_btn = self.profile_tab.copy_stats_btn
        self.prof_get_all_plane_data = self.profile_tab.get_all_plane_data
        # Connect buttons to existing handlers
        self.prof_orientation_btn.clicked.connect(self._on_prof_orientation_toggle)
        self.prof_xmode_btn.clicked.connect(self._on_prof_xmode_toggle)
        self.prof_compute_method_combo.currentTextChanged.connect(self._on_prof_compute_method_combo)
        self.prof_copy_btn.clicked.connect(self.copy_profile_to_clipboard)
        self.prof_copy_stats_btn.clicked.connect(self.copy_prof_stats_to_clipboard)
        self.tabs.addTab(self.profile_tab, "Profile")

        # Histogram tab (modular)
        self.hist_tab = HistogramTab(
            PYQTGRAPH_AVAILABLE,
            on_save_viewbox_state=lambda vb: self._save_viewbox_state(vb, "hist"),
            on_connect_plot_controls=lambda plot_item: self._connect_plotitem_controls(plot_item, "hist"),
            on_channel_changed=lambda checks: self._on_channel_changed(checks),
            on_spinbox_changed=lambda new_value: self._on_spinbox_changed(new_value),
            on_spinbox_bar_alpha_changed=lambda new_value: self._on_spinbox_bar_alpha_changed(new_value),
            parent=self,
        )
        self.hist_widget = self.hist_tab.hist_widget
        self.hist_stats_table = self.hist_tab.stats_table
        self.hist_config_mode_btn = self.hist_tab.config_mode_btn
        self.hist_config_reset_btn = self.hist_tab.config_reset_btn
        self.hist_chart_kind_combo = self.hist_tab.chart_kind_combo
        self.hist_bar_alpha_spin_box = self.hist_tab.bar_alpha_spin_box
        self.hist_copy_btn = self.hist_tab.copy_btn
        self.hist_copy_stats_btn = self.hist_tab.copy_stats_btn
        self.hist_get_all_plane_data = self.hist_tab.get_all_plane_data
        # Connect buttons to existing handlers
        self.hist_chart_kind_combo.currentTextChanged.connect(self._on_hist_chart_kind_combo)
        self.hist_config_mode_btn.clicked.connect(self.hist_config_mode_toggle)
        self.hist_config_reset_btn.clicked.connect(self.hist_config_reset)
        self.hist_copy_btn.clicked.connect(self.copy_histogram_to_clipboard)
        self.hist_copy_stats_btn.clicked.connect(self.copy_hist_stats_to_clipboard)
        self.tabs.addTab(self.hist_tab, "Histogram")

        # ステータスバー
        self.status = QStatusBar()
        self.status.setStyleSheet("QStatusBar, QLabel { font-size: 14px; }")
        main.addWidget(self.status)

        self.tabs_info = QLabel()
        left_container = QWidget()
        left_layout = QHBoxLayout(left_container)
        left_layout.setContentsMargins(15, 0, 15, 0)
        left_layout.setSpacing(8)
        left_layout.addWidget(self.tabs_info)
        self.status.addWidget(left_container)

        self.hist_tab.status_changed.connect(self.tabs_info.setText)
        self.profile_tab.status_changed.connect(self.tabs_info.setText)

    # Note: Close button is intentionally omitted for a modeless dialog

    def update_window_title(self, *args):
        """親の status_roi_area の値からウィンドウタイトルを更新する"""
        base_title = "解析ビュー"

        if self.viewer and hasattr(self.viewer, "status_roi_area"):
            roi_text = self.viewer.status_roi_area.text()
            if roi_text:
                self.setWindowTitle(f"{base_title} | ROI={roi_text}")
                return  # ← update_window_title 内での return はOKです！

        # ROI情報が無い場合のデフォルトタイトル
        self.setWindowTitle(base_title)

    def changeEvent(self, event):
        """Handle window state changes to preserve position during minimize/restore."""
        if event.type() == QEvent.WindowStateChange:
            if self.isMinimized():
                # Save current position before minimize
                AnalysisDialog._position_before_minimize = self.pos()
            elif event.oldState() & Qt.WindowMinimized and AnalysisDialog._position_before_minimize is not None:
                self.move(AnalysisDialog._position_before_minimize)
        super().changeEvent(event)

    def moveEvent(self, event):
        # Save geometry whenever the dialog is moved
        with contextlib.suppress(Exception):
            AnalysisDialog._saved_geometry = self.saveGeometry()
        super().moveEvent(event)

    def resizeEvent(self, event):
        # Save geometry whenever the dialog is resized
        with contextlib.suppress(Exception):
            AnalysisDialog._saved_geometry = self.saveGeometry()
        super().resizeEvent(event)

    def set_image_and_rect(
        self,
        image_array: np.ndarray | None,
        image_rect: QRect | None,
        image_path: str | None = None,
    ):
        """Update the dialog display content with new image data and selection rectangle.

        This method is expected to be called frequently from outside (parent viewer),
        and it calls `update_contents` to rebuild the internal display after updating the model.

        Arguments:
            image_array: NumPy array of the image or selection
            image_rect: Selection rectangle in image（QRect）
            image_path: File path of the image (used for metadata extraction)
        """
        self.image_array = image_array
        self.image_rect = image_rect
        if image_path is not None:
            self.image_path = image_path

        self.update_contents()

    def set_current_tab(self, tab):
        """Switch tabs by name（prefix of 'Histogram','Profile','Info'  or index）

        Arguments:
            tab: String tab name or index（int）
        """
        if tab is None:
            return
        if isinstance(tab, int):
            if 0 <= tab < self.tabs.count():
                self.tabs.setCurrentIndex(tab)
            return
        t = str(tab).lower()
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i).lower().startswith(t):
                self.tabs.setCurrentIndex(i)
                return

    def _on_channel_changed(self, new_checks: list[bool]):
        """Called when channel checkboxes change in tabs.

        Parameters
        ----------
        new_checks: list[bool]
            New checkbox states
        """
        self.channel_checks = new_checks
        self.update_contents()

    def _on_spinbox_changed(self, new_value: float):
        """Called when the double spin box value changes.

        Parameters
        ----------
        new_value: float
            New spin box value
        """
        self.spinbox_value = new_value
        self.update_contents()

    def _on_spinbox_bar_alpha_changed(self, new_value: int):
        self.spinbox_bar_alpha_value = new_value
        self.update_contents()

    def update_contents(self):
        """Update all tabs based on current image data / settings

        - Handle ROI region if it exits
        - Update metadata tab
        - Plot histogram / profile if pyqtgraph is availabel
        """
        arr = self.image_array
        if arr is None:
            self._update_metadata()
            return
        if self.image_rect is not None:
            x, y, w, h = (
                int(self.image_rect.x()),
                int(self.image_rect.y()),
                int(self.image_rect.width()),
                int(self.image_rect.height()),
            )
            arr = arr[y : y + h, x : x + w]
        else:
            arr = arr[0:1, 0:1]

        # Update metadata tab (always update when image changes)
        self._update_metadata()

        if not PYQTGRAPH_AVAILABLE:
            return

        # Ensure channel_checks length for current image
        if arr.ndim == 3 and arr.shape[2] > 1:
            nch = arr.shape[2]
            if not self.channel_checks:
                self.channel_checks = [True] * nch
            elif len(self.channel_checks) < nch:
                self.channel_checks.extend([True] * (nch - len(self.channel_checks)))
        else:
            nch = 1

        # Histogram: compute data and delegate to tab
        if self.hist_config_mode == "Histogram":
            bins = determine_hist_bins(arr, self.spinbox_value)
            hist_series = histogram_series(arr, bins=bins)
        elif self.hist_config_mode == "ECDF":
            hist_series = ecdf_series(arr)
        # Filter visible channels
        visible_hist_series = {}
        for label, (xs, ys) in hist_series.items():
            visible = True
            if label.startswith("C"):
                try:
                    cindex = int(label[1:])
                    visible = self.channel_checks[cindex]
                except Exception:
                    visible = True
            if visible:
                visible_hist_series[label] = (xs, ys)
        self.last_hist_data = hist_series  # store all for copy
        hist_stats = histogram_stats(arr.astype(np.float64), self.channel_checks)
        apply_log = self.plot_settings.get("hist", {}).get("log", False)
        # Check if image is integer type for histogram x-axis formatting
        is_integer_type = np.issubdtype(arr.dtype, np.integer)
        # Get channel colors with precedence:
        # 1) self.channel_colors (explicit override)
        # 2) if parent is a tiling dialog/window -> default palette per image (1ch=black)
        # 3) parent().channel_colors
        channel_colors = getattr(self, "channel_colors", None)
        if not channel_colors:
            is_tiling_parent = False
            try:
                p = self.parent()
                if p is not None:
                    cls = type(p)
                    mod = getattr(cls, "__module__", "").lower()
                    name = getattr(cls, "__name__", "").lower()
                    if "tiling" in mod or "tiling" in name:
                        is_tiling_parent = True
            except Exception:
                is_tiling_parent = False

            if is_tiling_parent:
                try:
                    nch_local = int(arr.shape[2]) if arr.ndim == 3 and arr.shape[2] > 1 else 1
                    colors = get_default_channel_colors(nch_local)
                    if nch_local == 1:
                        colors = [QColor(0, 0, 0)]
                    channel_colors = colors
                except Exception:
                    channel_colors = None
            if not channel_colors:
                try:
                    if hasattr(self.parent(), "channel_colors"):
                        channel_colors = self.parent().channel_colors
                except Exception:
                    channel_colors = None

        # Update channel checkboxes in tabs
        try:
            self.hist_tab.update_channel_checkboxes(nch, self.channel_checks, channel_colors)
            self.profile_tab.update_channel_checkboxes(nch, self.channel_checks, channel_colors)
        except Exception:
            pass

        # Build channel_color_map for stats table color swatches
        self.channel_color_map = {}
        if channel_colors:
            # Determine channel count
            nch_local = arr.shape[2] if arr.ndim == 3 and arr.shape[2] > 1 else 1
            for cindex in range(nch_local):
                if cindex < len(channel_colors):
                    color = channel_colors[cindex]
                    try:
                        r, g, b, _ = color.getRgb()
                    except Exception:
                        r, g, b = (127, 127, 127)
                    # Store both numeric and symbolic keys
                    self.channel_color_map[f"C{cindex}"] = (r, g, b)
                    self.channel_color_map[str(cindex)] = (r, g, b)
            # Intensity mapping (single-channel): always black
            if nch_local == 1:
                self.channel_color_map["I"] = (0, 0, 0)
                self.channel_color_map["0"] = (0, 0, 0)
                self.channel_color_map["C0"] = (0, 0, 0)
        else:
            # Fallback default palette
            default_palette = [
                (255, 0, 0),
                (0, 200, 0),
                (0, 102, 255),
                (127, 127, 127),
            ]
            nch_local = arr.shape[2] if arr.ndim == 3 and arr.shape[2] > 1 else 1
            for cindex in range(nch_local):
                rgb = default_palette[cindex] if cindex < len(default_palette) else (127, 127, 127)
                self.channel_color_map[f"C{cindex}"] = rgb
                self.channel_color_map[str(cindex)] = rgb
            if nch_local == 1:
                # 1ch: always black
                self.channel_color_map["I"] = (0, 0, 0)
                self.channel_color_map["0"] = (0, 0, 0)
                self.channel_color_map["C0"] = (0, 0, 0)
        self.hist_tab.update(
            visible_hist_series,
            hist_stats,
            apply_log=apply_log,
            is_integer_type=is_integer_type,
            channel_colors=channel_colors,
            chart_kind=self.hist_chart_kind,
            bar_alpha=self.spinbox_bar_alpha_value,
        )

        # Profile: compute data and delegate to tab
        pseries = profile_series(arr, orientation=self.profile_orientation, method=self.profile_compute_method)
        visible_prof_series = {}
        for label, prof in pseries.items():
            if self.x_mode == "absolute" and self.image_rect is not None:
                offset = get_profile_offset(self.image_rect, self.profile_orientation)
                xs2 = np.arange(prof.size) + offset
            else:
                xs2 = np.arange(prof.size)
            visible = True
            if label.startswith("C"):
                try:
                    cindex = int(label[1:])
                    visible = self.channel_checks[cindex]
                except Exception:
                    visible = True
            if visible:
                visible_prof_series[label] = (xs2, prof)
        # Rebuild full last_profile_data for copy (include all channels)
        self.last_profile_data = {}
        for label, prof in pseries.items():
            if self.x_mode == "absolute" and self.image_rect is not None:
                offset = get_profile_offset(self.image_rect, self.profile_orientation)
                xs2 = np.arange(prof.size) + offset
            else:
                xs2 = np.arange(prof.size)
            self.last_profile_data[label] = (xs2, prof)
        prof_stats = profile_stats(
            arr,
            orientation=self.profile_orientation,
            method=self.profile_compute_method,
            channel_checks=self.channel_checks,
        )
        # Use the same resolved channel_colors for profile tab
        self.profile_tab.update(
            visible_prof_series,
            prof_stats,
            self.profile_orientation,
            self.x_mode,
            self.profile_compute_method,
            channel_colors=channel_colors,
        )

        # Ensure both widgets are in true "Auto" state for axes, unless we have a saved ViewBox state
        if PYQTGRAPH_AVAILABLE:
            try:
                # Only perform autoRange if we don't already have a saved state for the viewboxes
                if not hasattr(self, "viewbox_full_hist"):
                    hist_vb = self.hist_widget.getViewBox()
                    hist_vb.autoRange()  # First fit to current data
                    hist_vb.enableAutoRange(axis=pg.ViewBox.XYAxes)  # Then enable auto for future
                if not hasattr(self, "viewbox_full_prof"):
                    prof_vb = self.prof_widget.getViewBox()
                    prof_vb.autoRange()  # First fit to current data
                    prof_vb.enableAutoRange(axis=pg.ViewBox.XYAxes)  # Then enable auto for future
            except Exception:
                pass

        # Re-apply any persisted plot settings (grid/log/auto-range, ViewBox state)
        self._apply_plot_settings()

    def _update_metadata(self):
        """Update the metadata tab with image file information in table format."""
        if not hasattr(self, "metadata_table"):
            return

        if self.image_path is None or not self.image_path:
            self.meta_tab.update([("Error", "No file path available")])
            self.last_metadata = []
            return

        try:
            # fall back to file path
            metadata = get_image_metadata(self.image_path, self.image_array)

            if not metadata:
                self.meta_tab.update([("Info", "No metadata available")])
                self.last_metadata = []
                return

            # Prepare data in order: Basic info first, then EXIF tags
            rows = []

            # 1. Basic information
            basic_keys = ["Filepath", "Format", "FileSize", "Size", "Channels", "DataType"]
            for key in basic_keys:
                if key in metadata:
                    value_str = str(metadata[key])
                    rows.append((key, value_str))

            # 2. EXIF tags
            exif_items = [(k, v) for k, v in metadata.items() if k not in basic_keys]
            for key, value in exif_items:
                value_str = str(value)
                rows.append((key, value_str))
                if key == "EXIF_ExposureTime":
                    # Add a human-readable exposure time
                    exposure_time = eval(value)
                    rows.append((" -> (seconds)", f"{exposure_time:.3e}"))

            # Store metadata for copying
            self.last_metadata = rows
            self.meta_tab.update(rows)

        except Exception as e:
            self.meta_tab.update([("Error", f"Error reading metadata: {e!s}")])
            self.last_metadata = []

    def hist_config_mode_toggle(self):
        if self.hist_config_mode == "Histogram":
            self.hist_config_mode = "ECDF"
            self.hist_config_mode_btn.setText("ECDF")
        else:
            self.hist_config_mode = "Histogram"
            self.hist_config_mode_btn.setText("Histogram")
        self.update_contents()

    def hist_config_reset(self):
        self._on_spinbox_changed(self.hist_tab.bin_step_spin_box_init)
        self.hist_tab.bin_step_spin_box.setValue(self.hist_tab.bin_step_spin_box_init)

    def copy_metadata_to_clipboard(self):
        """Copy metadata as comma-separated text to clipboard."""
        if not hasattr(self, "last_metadata") or not self.last_metadata:
            QMessageBox.information(self, "Copy", "No metadata to copy.")
            return

        # Create comma-separated format
        lines = ["Key,Value"]  # Header
        for key, value in self.last_metadata:
            lines.append(f"{key},{value}")

        text = "\n".join(lines)
        QGuiApplication.clipboard().setText(text)

    def copy_histogram_to_clipboard(self):
        """Copy histogram data as CSV to clipboard."""
        if not getattr(self, "last_hist_data", None):
            QMessageBox.information(self, "Copy", "No data.")
            return

        # Use numpy array operations for efficient data processing
        keys = list(self.last_hist_data.keys())

        # 最初のキー（keys[0]）から、共通の x 軸（中心値）を取り出し
        xs = np.array(self.last_hist_data[keys[0]][0]).flatten()

        if self.hist_config_mode == "Histogram":
            # ビンの刻み幅を計算して、開始位置と終了位置を計算
            bin_width = np.diff(xs)[0] if len(xs) > 1 else 1.0
            bin_starts = xs - (bin_width / 2)
            bin_ends = xs + (bin_width / 2)

            csv_data = {"bin_start": bin_starts, "bin_end": bin_ends, "bin_center": xs}
            cast_int_keys = keys  # ヒストグラムは度数データをintにキャスト

        elif self.hist_config_mode == "ECDF":
            csv_data = {"value": xs}
            cast_int_keys = None

        # 度数データ（Iなど）を合流させる
        for k in keys:
            csv_data[k] = np.array(self.last_hist_data[k][1]).flatten()

        text = series_to_csv(csv_data, cast_int_keys=cast_int_keys)
        QGuiApplication.clipboard().setText(text)

    def copy_profile_to_clipboard(self):
        """Copy profile data as CSV to clipboard."""
        if not getattr(self, "last_profile_data", None):
            QMessageBox.information(self, "Copy", "No data.")
            return

        # Use numpy array operations for efficient data processing
        keys = list(self.last_profile_data.keys())
        xs = self.last_profile_data[keys[0]][0]

        # 1. 最初に x軸（例: "x"）のデータを辞書に入れる
        csv_data = {"x address": xs} if self.profile_orientation == "h" else {"y address": xs}

        # 2. 残りの y軸シリーズ（float値）を同じ辞書に追加していく
        for k in keys:
            csv_data[k] = self.last_profile_data[k][1]

        # 3. 新しい series_to_csv を呼び出す（float値なので cast_int_keys は不要）
        text = series_to_csv(csv_data)
        QGuiApplication.clipboard().setText(text)

    def copy_hist_stats_to_clipboard(self):
        if not hasattr(self, "hist_stats_table"):
            QMessageBox.information(self, "Copy", "No histogram stats to copy.")
            return
        imgs = self.viewer.images
        current_id = self.viewer.current_index
        x, y, w, h = self.viewer.current_roi_rect.getRect()
        text = "path,ch,x_sta,y_sta,width,hight,mean,std,median,min,max,fano\n"

        targets = imgs if self.hist_get_all_plane_data.isChecked() else [imgs[current_id]]

        for img in targets:
            path = img.get("path")
            arr = img.get("base_array")
            height, width = arr.shape[:2]
            # 例外処理
            if x > width or (x + w) > width or y > height or (y + h) > height:
                continue

            if arr.ndim == 2:
                arr = arr[:, :, np.newaxis]

            for ch in range(arr.shape[2]):
                data = arr[:, :, ch]
                data_roi = data[y : y + h, x : x + w]
                mean, std, median, min, max, fano = calc_stats(data_roi)
                text += f"{path},{ch},{x},{y},{w},{h},{mean},{std},{median},{min},{max},{fano}\n"
        QGuiApplication.clipboard().setText(text)

    def copy_prof_stats_to_clipboard(self):
        if not hasattr(self, "prof_stats_table"):
            QMessageBox.information(self, "Copy", "No profile stats to copy.")
            return
        imgs = self.viewer.images
        current_id = self.viewer.current_index
        x, y, w, h = self.viewer.current_roi_rect.getRect()
        orientation = self.profile_orientation
        method = self.profile_compute_method
        text = "path,ch,x_sta,y_sta,width,hight,orientation,method,mean,std,median,min,max,fano\n"

        targets = imgs if self.prof_get_all_plane_data.isChecked() else [imgs[current_id]]

        for img in targets:
            path = img.get("path")
            arr = img.get("base_array")
            height, width = arr.shape[:2]
            # 例外処理
            if x > width or (x + w) > width or y > height or (y + h) > height:
                continue

            if arr.ndim == 2:
                arr = arr[:, :, np.newaxis]

            for ch in range(arr.shape[2]):
                data = arr[:, :, ch]
                data_roi = data[y : y + h, x : x + w]
                prof_roi = compute_profile_1d(data_roi, orientation, method)
                mean, std, median, min, max, fano = calc_stats(prof_roi)
                text += f"{path},{ch},{x},{y},{w},{h},{orientation},{method},{mean},{std},{median},{min},{max},{fano}\n"
        QGuiApplication.clipboard().setText(text)

    def _on_prof_orientation_toggle(self):
        """Toggle profile orientation between horizontal and vertical."""
        if self.profile_orientation == "h":
            self.profile_orientation = "v"
            self.prof_orientation_btn.setText("Vertical")
        else:
            self.profile_orientation = "h"
            self.prof_orientation_btn.setText("Horizontal")
        self.update_contents()

    def _on_prof_xmode_toggle(self):
        """Toggle x-axis mode between relative and absolute."""
        if self.x_mode == "relative":
            self.x_mode = "absolute"
            self.prof_xmode_btn.setText("Absolute")
        else:
            self.x_mode = "relative"
            self.prof_xmode_btn.setText("Relative")
        self.update_contents()

    def _on_prof_compute_method_combo(self):
        """Handle changes to the profile computation method selected in the combo box."""
        self.profile_compute_method = self.prof_compute_method_combo.currentText()
        self.update_contents()

    def _on_hist_chart_kind_combo(self):
        self.hist_chart_kind = self.hist_chart_kind_combo.currentText()
        if self.hist_chart_kind == "Bar":
            self.hist_bar_alpha_spin_box.setEnabled(True)
        else:
            self.hist_bar_alpha_spin_box.setEnabled(False)
        self.update_contents()

    def _on_external_log_toggled(self, checked: bool):
        # When user toggles Log Y via pyqtgraph menu, update store and replot
        try:
            self.plot_settings.setdefault("hist", {})["log"] = bool(checked)
            self.update_contents()
        except Exception:
            pass

    def _connect_plotitem_controls(self, plot_item, which: str):
        # Thin wrapper delegating to plotting helper
        pg_connect_plot_controls(
            plot_item,
            which,
            self.plot_settings,
            on_hist_log_changed=lambda: self._on_external_log_toggled(
                self.plot_settings.get("hist", {}).get("log", False)
            ),
        )

    def _apply_plot_settings(self):
        # Thin wrapper delegating to plotting helper
        try:
            if hasattr(self, "hist_widget") and self.hist_widget is not None:
                pg_apply_plot_settings(
                    self.hist_widget, "hist", self.plot_settings, getattr(self, "viewbox_full_hist", None)
                )
            if hasattr(self, "prof_widget") and self.prof_widget is not None:
                pg_apply_plot_settings(
                    self.prof_widget, "prof", self.plot_settings, getattr(self, "viewbox_full_prof", None)
                )
        except Exception:
            pass

    def _save_viewbox_state(self, vb, which: str):
        try:
            full_state = pg_save_viewbox_state(vb)
            if full_state is not None:
                setattr(self, f"viewbox_full_{which}", full_state)
        except Exception:
            pass

    def keyPressEvent(self, event):
        """Override ESC key to prevent closing dialog.

        ESC key will clear focus from spinbox/input fields without closing the dialog.
        """
        if event.key() == Qt.Key_Escape:
            # If focus is on an input widget, clear focus to finish editing
            focused_widget = self.focusWidget()
            if focused_widget and isinstance(focused_widget, (QSpinBox, QDoubleSpinBox, QLineEdit)):
                focused_widget.clearFocus()
                event.accept()
                return
            # Otherwise, don't close dialog - just ignore
            event.ignore()
            return
        super().keyPressEvent(event)
