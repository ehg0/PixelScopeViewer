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

from typing import Optional
import numpy as np

from PySide6.QtCore import QRect, Qt
from ....core.image_io import get_image_metadata
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTabWidget,
    QPushButton,
    QDialogButtonBox,
    QWidget,
    QMessageBox,
    QTableWidget,
)
from PySide6.QtGui import QGuiApplication

try:
    import pyqtgraph as pg
    from pyqtgraph import PlotWidget

    PYQTGRAPH_AVAILABLE = True

except ImportError:
    pg = None
    PlotWidget = None
    PYQTGRAPH_AVAILABLE = False

from .widgets import ChannelsDialog, CopyableTableWidget
from .tabs.metadata_tab import MetadataTab
from .tabs.profile_tab import ProfileTab
from .tabs.histogram_tab import HistogramTab
from .core import (
    determine_hist_bins,
    histogram_series,
    profile_series,
    get_profile_offset,
    histogram_stats,
    profile_stats,
)
from .exporting import series_to_csv, table_to_csv, selection_to_csv
from .plotting import (
    save_viewbox_state as pg_save_viewbox_state,
    apply_plot_settings as pg_apply_plot_settings,
    connect_plot_controls as pg_connect_plot_controls,
    show_default_context_menu as pg_show_default_context_menu,
)


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

    def __init__(
        self,
        parent=None,
        image_array: Optional[np.ndarray] = None,
        image_rect: Optional[QRect] = None,
        image_path: Optional[str] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Analysis")
        self.resize(900, 600)
        self.image_array = image_array
        self.image_rect = image_rect
        self.image_path = image_path

        # state
        self.profile_orientation = "h"  # "h", "v", or "d" (diagonal)
        self.x_mode = "relative"
        self.hist_yscale = "linear"
        self.channel_checks: list[bool] = []

        self.last_hist_data = {}
        self.last_profile_data = {}

        # Persisted plot settings for histogram/profile (kept across image switches)
        # keys: 'hist' and 'prof' with values for grid/log/autorange
        self.plot_settings = {
            "hist": {"grid": True, "log": False, "auto_range": True},
            "prof": {"grid": True, "auto_range": True},
        }

        # Keep references to channel dialogs to prevent multiple instances
        self._hist_channels_dialog = None
        self._prof_channels_dialog = None

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
            parent=self,
        )
        self.prof_widget = self.profile_tab.prof_widget
        self.prof_stats_table = self.profile_tab.prof_stats_table
        self.prof_channels_btn = self.profile_tab.channels_btn
        self.prof_orientation_btn = self.profile_tab.orientation_btn
        self.prof_xmode_btn = self.profile_tab.xmode_btn
        self.prof_copy_btn = self.profile_tab.copy_btn
        self.prof_copy_stats_btn = self.profile_tab.copy_stats_btn
        # Connect buttons to existing handlers
        self.prof_channels_btn.clicked.connect(self._on_prof_channels)
        self.prof_orientation_btn.clicked.connect(self._on_prof_orientation_toggle)
        self.prof_xmode_btn.clicked.connect(self._on_prof_xmode_toggle)
        self.prof_copy_btn.clicked.connect(self.copy_profile_to_clipboard)
        self.prof_copy_stats_btn.clicked.connect(self.copy_prof_stats_to_clipboard)
        self.tabs.addTab(self.profile_tab, "Profile")

        # Histogram tab (modular)
        self.hist_tab = HistogramTab(
            PYQTGRAPH_AVAILABLE,
            on_save_viewbox_state=lambda vb: self._save_viewbox_state(vb, "hist"),
            on_connect_plot_controls=lambda plot_item: self._connect_plotitem_controls(plot_item, "hist"),
            parent=self,
        )
        self.hist_widget = self.hist_tab.hist_widget
        self.hist_stats_table = self.hist_tab.stats_table
        self.hist_channels_btn = self.hist_tab.channels_btn
        self.hist_copy_btn = self.hist_tab.copy_btn
        self.hist_copy_stats_btn = self.hist_tab.copy_stats_btn
        # Connect buttons to existing handlers
        self.hist_channels_btn.clicked.connect(self._on_hist_channels)
        self.hist_copy_btn.clicked.connect(self.copy_histogram_to_clipboard)
        self.hist_copy_stats_btn.clicked.connect(self.copy_hist_stats_to_clipboard)
        self.tabs.addTab(self.hist_tab, "Histogram")

    # Note: Close button is intentionally omitted for a modeless dialog

    def moveEvent(self, event):
        # Save geometry whenever the dialog is moved
        try:
            AnalysisDialog._saved_geometry = self.saveGeometry()
        except Exception:
            pass
        super().moveEvent(event)

    def resizeEvent(self, event):
        # Save geometry whenever the dialog is resized
        try:
            AnalysisDialog._saved_geometry = self.saveGeometry()
        except Exception:
            pass
        super().resizeEvent(event)

    def set_image_and_rect(
        self,
        image_array: Optional[np.ndarray],
        image_rect: Optional[QRect],
        image_path: Optional[str] = None,
    ):
        """ダイアログの表示内容を新しい画像データや選択矩形で更新します。

        このメソッドは外部（親ビューア）から頻繁に呼ばれる想定で、
        モデルを更新したあと内部表示を再構築する `update_contents` を呼び出します。

        引数:
            image_array: 画像または選択領域の NumPy 配列
            image_rect: 画像座標系での選択矩形（QRect）
            image_path: 画像ファイルのパス（メタデータ取得に利用）
        """
        self.image_array = image_array
        self.image_rect = image_rect
        if image_path is not None:
            self.image_path = image_path

        # Update channel dialogs if they exist and image channel count changed
        if image_array is not None:
            nch = image_array.shape[2] if image_array.ndim == 3 else 1
            if self._hist_channels_dialog is not None and self._hist_channels_dialog.isVisible():
                self._hist_channels_dialog.update_for_new_image(nch, self.channel_checks)
            if self._prof_channels_dialog is not None and self._prof_channels_dialog.isVisible():
                self._prof_channels_dialog.update_for_new_image(nch, self.channel_checks)

        self.update_contents()

    def set_current_tab(self, tab):
        """タブを名前（'Histogram','Profile','Info' の先頭部分一致）またはインデックスで切り替えます。

        引数:
            tab: タブ名の文字列あるいはインデックス（int）
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

    def _on_hist_channels(self):
        """ヒストグラム用のチャネル選択ダイアログを作成して表示します。

        すでに画像データがない場合は何もしません。
        """
        if self.image_array is None:
            return

        # If dialog already exists and is visible, just raise it
        if self._hist_channels_dialog is not None and self._hist_channels_dialog.isVisible():
            self._hist_channels_dialog.raise_()
            self._hist_channels_dialog.activateWindow()
            return

        nch = self.image_array.shape[2] if self.image_array.ndim == 3 else 1

        def immediate_update(new_checks):
            """Callback for immediate graph update when checkboxes change."""
            self.channel_checks = new_checks
            self.update_contents()

        # Create and show modeless dialog with immediate updates
        dlg = ChannelsDialog(self, nch, self.channel_checks, callback=immediate_update)
        self._hist_channels_dialog = dlg

        # Clean up reference when dialog is closed
        dlg.finished.connect(lambda: setattr(self, "_hist_channels_dialog", None))

        # Position dialog near the histogram channels button
        button_pos = self.hist_channels_btn.mapToGlobal(self.hist_channels_btn.rect().topRight())
        dlg.move(button_pos.x() + 10, button_pos.y())

        dlg.show()  # Show modeless dialog without blocking

    def _on_prof_channels(self):
        """プロファイル用のチャネル選択ダイアログを作成して表示します。

        すでに画像データがない場合は何もしません。
        """
        if self.image_array is None:
            return

        # If dialog already exists and is visible, just raise it
        if self._prof_channels_dialog is not None and self._prof_channels_dialog.isVisible():
            self._prof_channels_dialog.raise_()
            self._prof_channels_dialog.activateWindow()
            return

        nch = self.image_array.shape[2] if self.image_array.ndim == 3 else 1

        def immediate_update(new_checks):
            """Callback for immediate graph update when checkboxes change."""
            self.channel_checks = new_checks
            self.update_contents()

        # Create and show modeless dialog with immediate updates
        dlg = ChannelsDialog(self, nch, self.channel_checks, callback=immediate_update)
        self._prof_channels_dialog = dlg

        # Clean up reference when dialog is closed
        dlg.finished.connect(lambda: setattr(self, "_prof_channels_dialog", None))

        # Position dialog near the profile channels button
        button_pos = self.prof_channels_btn.mapToGlobal(self.prof_channels_btn.rect().topRight())
        dlg.move(button_pos.x() + 10, button_pos.y())

        dlg.show()  # Show modeless dialog without blocking

    def update_contents(self):
        """現在の画像データ／設定をもとに全タブの内容を再描画します。

        - ROI領域が存在する場合はその領域のみを扱います
        - メタデータタブは常に更新されます
        - pyqtgraph が利用可能な場合はヒストグラム／プロファイルをプロットします
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

        # Histogram: compute data and delegate to tab
        bins = determine_hist_bins(arr)
        hist_series = histogram_series(arr, bins=bins)
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
        hist_stats = histogram_stats(arr, self.channel_checks)
        apply_log = self.plot_settings.get("hist", {}).get("log", False)
        # Check if image is integer type for histogram x-axis formatting
        is_integer_type = np.issubdtype(arr.dtype, np.integer)
        # Get channel colors from parent viewer
        channel_colors = None
        try:
            if hasattr(self.parent(), "channel_colors"):
                channel_colors = self.parent().channel_colors
        except Exception:
            pass
        self.hist_tab.update(
            visible_hist_series,
            hist_stats,
            self.plot_settings,
            apply_log=apply_log,
            is_integer_type=is_integer_type,
            channel_colors=channel_colors,
        )

        # Profile: compute data and delegate to tab
        pseries = profile_series(arr, orientation=self.profile_orientation)
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
        prof_stats = profile_stats(arr, orientation=self.profile_orientation, channel_checks=self.channel_checks)
        # Get channel colors from parent viewer (same as histogram)
        self.profile_tab.update(
            visible_prof_series, prof_stats, self.profile_orientation, self.x_mode, channel_colors=channel_colors
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
            metadata = get_image_metadata(self.image_path)

            if not metadata:
                self.meta_tab.update([("Info", "No metadata available")])
                self.last_metadata = []
                return

            # Prepare data in order: Basic info first, then EXIF tags
            rows = []

            # 1. Basic information (from PIL)
            basic_keys = ["Filepath", "Format", "Size", "Channels", "DataType"]
            for key in basic_keys:
                if key in metadata:
                    value_str = str(metadata[key])
                    rows.append((key, value_str))

            # 2. EXIF tags (sorted alphabetically)
            exif_items = [(k, v) for k, v in metadata.items() if k not in basic_keys]
            for key, value in sorted(exif_items):
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
            self.meta_tab.update([("Error", f"Error reading metadata: {str(e)}")])
            self.last_metadata = []

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
        QMessageBox.information(self, "Copy", f"Copied {len(self.last_metadata)} metadata entries to clipboard.")

    def copy_histogram_to_clipboard(self):
        """Copy histogram data as CSV to clipboard."""
        if not getattr(self, "last_hist_data", None):
            QMessageBox.information(self, "Copy", "No data.")
            return

        # Use numpy array operations for efficient data processing
        keys = list(self.last_hist_data.keys())
        xs = self.last_hist_data[keys[0]][0]

        # Use shared exporter (cast to int for histogram counts)
        series = {k: self.last_hist_data[k][1] for k in keys}
        text = series_to_csv(xs, series, cast_int=True)
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copy", "Histogram copied to clipboard.")

    def copy_profile_to_clipboard(self):
        """Copy profile data as CSV to clipboard."""
        if not getattr(self, "last_profile_data", None):
            QMessageBox.information(self, "Copy", "No data.")
            return

        # Use numpy array operations for efficient data processing
        keys = list(self.last_profile_data.keys())
        xs = self.last_profile_data[keys[0]][0]

        # Use shared exporter (float values)
        series = {k: self.last_profile_data[k][1] for k in keys}
        text = series_to_csv(xs, series, cast_int=False)
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copy", "Profile copied to clipboard.")

    def _table_selection_to_csv(self, table: QTableWidget) -> str:
        """Convert the selected region of a QTableWidget to CSV text.

        If multiple non-contiguous ranges are selected, the first range is used.
        """
        # Delegate to shared exporter
        return selection_to_csv(table)

    def _table_to_csv(self, table: QTableWidget) -> str:
        """Export entire table (with header) to CSV text."""
        return table_to_csv(table)

    def copy_hist_stats_to_clipboard(self):
        if not hasattr(self, "hist_stats_table"):
            QMessageBox.information(self, "Copy", "No histogram stats to copy.")
            return
        text = self._table_to_csv(self.hist_stats_table)
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copy", "Histogram stats copied to clipboard.")

    def copy_prof_stats_to_clipboard(self):
        if not hasattr(self, "prof_stats_table"):
            QMessageBox.information(self, "Copy", "No profile stats to copy.")
            return
        text = self._table_to_csv(self.prof_stats_table)
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copy", "Profile stats copied to clipboard.")

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

    def _show_plot_context_menu(self, widget, which: str, pos):
        # Delegate to plotting helper
        pg_show_default_context_menu(widget, pos)

    def _on_external_grid_toggled(self, checked: bool):
        # Keep backward compatibility: grid affects both plots
        val = bool(checked)
        try:
            self.plot_settings.setdefault("hist", {})["grid"] = val
            self.plot_settings.setdefault("prof", {})["grid"] = val
        except Exception:
            pass

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
        from PySide6.QtWidgets import QSpinBox, QDoubleSpinBox, QLineEdit

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
