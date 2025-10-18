"""Analysis dialog with tabbed interface for image analysis.

This module provides the main AnalysisDialog which displays:
- Info tab: Selection size and position
- Histogram tab: Intensity histogram with logarithmic scale toggle
- Profile tab: Line profile (horizontal/vertical/diagonal) with absolute/relative modes
- Metadata tab: Image metadata in table format with EXIF information

The dialog supports pyqtgraph-based interactive plots with double-click
gestures for toggling plot modes. If pyqtgraph is not available, the
histogram and profile tabs will show empty placeholders.

Dependencies:
    - pyqtgraph (optional): For fast histogram and profile plotting
    - numpy: For data processing
    - exifread: For comprehensive EXIF metadata reading
"""

from typing import Optional
import numpy as np

from PySide6.QtCore import QRect
from ....core.image_io import get_image_metadata
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QTextBrowser,
    QPushButton,
    QDialogButtonBox,
    QWidget,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
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

from .controls import ChannelsDialog, RangesDialog
from .widgets import CopyableTableWidget


class AnalysisDialog(QDialog):
    """Main analysis dialog with tabbed interface for Info, Histogram, and Profile.

    This dialog provides three tabs for analyzing image selections:

    1. Info Tab:
       - Displays selection dimensions and position

    2. Histogram Tab:
       - Shows intensity distribution across all channels
       - Left double-click: Toggle linear/logarithmic Y scale
       - Customizable via "Channels..." and "Axis ranges..." buttons
       - "Copy data" exports histogram as CSV to clipboard

    3. Profile Tab:
       - Shows averaged intensity profile along a direction
       - Left double-click: Toggle horizontal/vertical orientation
       - Right double-click: Toggle relative/absolute X axis
       - Customizable via "Channels..." and "Axis ranges..." buttons
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
        self.manual_ranges = (None, None, None, None)
        self.last_hist_data = {}
        self.last_profile_data = {}

        # For time-based double-click detection (fallback when event.dblclick not available)
        self._last_click_time = {}
        self._double_click_interval = 0.4  # seconds

        self._build_ui()

        try:
            if hasattr(self, "hist_widget") and self.hist_widget is not None:
                self.hist_widget.scene().sigMouseClicked.connect(self._on_hist_click)
            if hasattr(self, "prof_widget") and self.prof_widget is not None:
                self.prof_widget.scene().sigMouseClicked.connect(self._on_profile_click)
        except Exception:
            pass

        if self.image_array is not None:
            self.update_contents()

    def _build_ui(self):
        main = QVBoxLayout(self)
        self.tabs = QTabWidget()
        main.addWidget(self.tabs)

        # Info tab
        info_tab = QWidget()
        il = QVBoxLayout(info_tab)
        self.info_browser = QTextBrowser()
        self.info_browser.setReadOnly(True)
        il.addWidget(self.info_browser)
        self.tabs.addTab(info_tab, "Info")

        # Metadata tab
        metadata_tab = QWidget()
        ml = QVBoxLayout(metadata_tab)

        # Create table for metadata display with Ctrl+C support
        self.metadata_table = CopyableTableWidget()
        self.metadata_table.setColumnCount(2)
        self.metadata_table.setHorizontalHeaderLabels(["Key", "Value"])
        self.metadata_table.horizontalHeader().setStretchLastSection(True)
        self.metadata_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.metadata_table.setEditTriggers(QTableWidget.NoEditTriggers)  # 編集不可
        self.metadata_table.setSelectionMode(QTableWidget.ExtendedSelection)  # 複数選択可能
        self.metadata_table.setSelectionBehavior(QTableWidget.SelectItems)  # セル単位で選択
        ml.addWidget(self.metadata_table)

        # Add copy button
        self.metadata_copy_btn = QPushButton("クリップボードにコピー")
        self.metadata_copy_btn.clicked.connect(self.copy_metadata_to_clipboard)
        ml.addWidget(self.metadata_copy_btn)

        self.tabs.addTab(metadata_tab, "Metadata")

        # Profile tab
        prof_tab = QWidget()
        pl = QHBoxLayout(prof_tab)
        if PYQTGRAPH_AVAILABLE:
            self.prof_widget = PlotWidget()
            self.prof_widget.setLabel("left", "Intensity")
            self.prof_widget.setLabel("bottom", "Position")

            # Style configuration for better UI integration
            self.prof_widget.setBackground("white")
            self.prof_widget.showGrid(x=True, y=True, alpha=0.2)
            self.prof_widget.getAxis("left").setPen(pg.mkPen(color="#bdc3c7", width=1))
            self.prof_widget.getAxis("bottom").setPen(pg.mkPen(color="#bdc3c7", width=1))
            self.prof_widget.getAxis("left").setTextPen(pg.mkPen(color="#2c3e50"))
            self.prof_widget.getAxis("bottom").setTextPen(pg.mkPen(color="#2c3e50"))
            # Add subtle border
            self.prof_widget.setStyleSheet("QWidget { border: 1px solid #bdc3c7; }")

            # Enable right-click menu but disable drag operations
            self.prof_widget.setMenuEnabled(True)
            # Disable all mouse drag interactions while preserving right-click
            view_box = self.prof_widget.getViewBox()
            view_box.setMouseEnabled(x=False, y=False)  # Disable mouse drag/zoom
            view_box.enableAutoRange(enable=False)  # Prevent auto-ranging

            pl.addWidget(self.prof_widget, 1)
        else:
            self.prof_widget = None
        pv = QVBoxLayout()
        self.prof_channels_btn = QPushButton("Channels...")
        self.prof_channels_btn.clicked.connect(self._on_prof_channels)
        pv.addWidget(self.prof_channels_btn)
        self.prof_ranges_btn = QPushButton("Axis ranges...")
        self.prof_ranges_btn.clicked.connect(self._on_ranges)
        pv.addWidget(self.prof_ranges_btn)
        self.prof_copy_btn = QPushButton("Copy data")
        self.prof_copy_btn.clicked.connect(self.copy_profile_to_clipboard)
        pv.addWidget(self.prof_copy_btn)
        pv.addStretch(1)
        pl.addLayout(pv)
        self.tabs.addTab(prof_tab, "Profile")

        # Histogram tab
        hist_tab = QWidget()
        hl = QHBoxLayout(hist_tab)
        if PYQTGRAPH_AVAILABLE:
            self.hist_widget = PlotWidget()
            self.hist_widget.setLabel("left", "Count")
            self.hist_widget.setLabel("bottom", "Intensity")

            # Style configuration for better UI integration
            self.hist_widget.setBackground("white")
            self.hist_widget.showGrid(x=True, y=True, alpha=0.2)
            self.hist_widget.getAxis("left").setPen(pg.mkPen(color="#bdc3c7", width=1))
            self.hist_widget.getAxis("bottom").setPen(pg.mkPen(color="#bdc3c7", width=1))
            self.hist_widget.getAxis("left").setTextPen(pg.mkPen(color="#2c3e50"))
            self.hist_widget.getAxis("bottom").setTextPen(pg.mkPen(color="#2c3e50"))
            # Add subtle border
            self.hist_widget.setStyleSheet("QWidget { border: 1px solid #bdc3c7; }")

            # Enable right-click menu but disable drag operations
            self.hist_widget.setMenuEnabled(True)
            # Disable all mouse drag interactions while preserving right-click
            view_box = self.hist_widget.getViewBox()
            view_box.setMouseEnabled(x=False, y=False)  # Disable mouse drag/zoom
            view_box.enableAutoRange(enable=False)  # Prevent auto-ranging

            hl.addWidget(self.hist_widget, 1)
        else:
            self.hist_widget = None

        vcol = QVBoxLayout()
        self.hist_channels_btn = QPushButton("Channels...")
        self.hist_channels_btn.clicked.connect(self._on_hist_channels)
        vcol.addWidget(self.hist_channels_btn)
        self.hist_ranges_btn = QPushButton("Axis ranges...")
        self.hist_ranges_btn.clicked.connect(self._on_ranges)
        vcol.addWidget(self.hist_ranges_btn)
        self.hist_copy_btn = QPushButton("Copy data")
        self.hist_copy_btn.clicked.connect(self.copy_histogram_to_clipboard)
        vcol.addWidget(self.hist_copy_btn)
        vcol.addStretch(1)
        hl.addLayout(vcol)
        self.tabs.addTab(hist_tab, "Histogram")

        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.rejected.connect(self.reject)
        box.accepted.connect(self.accept)
        main.addWidget(box)

    def set_image_and_rect(
        self, image_array: Optional[np.ndarray], image_rect: Optional[QRect], image_path: Optional[str] = None
    ):
        """Update the dialog with new image data and/or selection rectangle."""
        self.image_array = image_array
        self.image_rect = image_rect
        if image_path is not None:
            self.image_path = image_path
        self.update_contents()

    def set_current_tab(self, tab):
        """Set current tab by name ('Histogram','Profile','Info') or index."""
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
        if self.image_array is None:
            return
        nch = self.image_array.shape[2] if self.image_array.ndim == 3 else 1

        def immediate_update(new_checks):
            """Callback for immediate graph update when checkboxes change."""
            self.channel_checks = new_checks
            self.update_contents()

        # Create and show modeless dialog with immediate updates
        dlg = ChannelsDialog(self, nch, self.channel_checks, callback=immediate_update)
        dlg.show()  # Show modeless dialog without blocking

    def _on_prof_channels(self):
        # reuse histogram channels handler for profile
        self._on_hist_channels()

    def _on_ranges(self):
        xmin, xmax, ymin, ymax = self.manual_ranges
        dlg = RangesDialog(self, xmin, xmax, ymin, ymax)
        if dlg.exec() == QDialog.Accepted:
            self.manual_ranges = dlg.results()
            self.update_contents()

    def update_contents(self):
        """Refresh all tabs with current image data and settings."""
        arr = self.image_array
        if arr is None:
            self.info_browser.setPlainText("No data")
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

        h, w = arr.shape[:2]
        info_lines = [f"Selection size: {w} x {h}"]
        if self.image_rect is not None:
            info_lines.append(f"Start: ({int(self.image_rect.x())}, {int(self.image_rect.y())})")
        self.info_browser.setPlainText("\n".join(info_lines))

        # Update metadata tab (always update when image changes)
        self._update_metadata()

        if not PYQTGRAPH_AVAILABLE:
            return

        # Histogram
        self.hist_widget.clear()
        self.last_hist_data = {}
        # Professional color palette for better UI integration
        colors = ["#e74c3c", "#2ecc71", "#3498db", "#34495e"]  # Red, Green, Blue, Dark gray

        # Store data for range calculation
        all_x_data = []
        all_y_data = []

        if arr.ndim == 3 and arr.shape[2] > 1:
            nch = arr.shape[2]
            if not self.channel_checks:
                self.channel_checks = [True] * nch
            for c in range(nch):
                data = arr[:, :, c].ravel()
                hist, bins = np.histogram(data, bins=256, range=(0, 255))
                xs = (bins[:-1] + bins[1:]) / 2.0
                self.last_hist_data[f"C{c}"] = (xs, hist)
                all_x_data.extend(xs)
                all_y_data.extend(hist)
                if self.channel_checks[c]:
                    # Thicker line with small dots
                    pen = pg.mkPen(color=colors[c] if c < len(colors) else "#7f8c8d", width=3)
                    symbol_brush = pg.mkBrush(color=colors[c] if c < len(colors) else "#7f8c8d")
                    self.hist_widget.plot(
                        xs, hist, pen=pen, symbol="o", symbolSize=4, symbolBrush=symbol_brush, name=f"C{c}"
                    )
        else:
            gray = arr if arr.ndim == 2 else arr[:, :, 0]
            hist, bins = np.histogram(gray.ravel(), bins=256, range=(0, 255))
            xs = (bins[:-1] + bins[1:]) / 2.0
            self.last_hist_data["I"] = (xs, hist)
            all_x_data.extend(xs)
            all_y_data.extend(hist)
            # Thicker line with small dots
            pen = pg.mkPen(color="#34495e", width=3)
            symbol_brush = pg.mkBrush(color="#34495e")
            self.hist_widget.plot(
                xs, hist, pen=pen, symbol="o", symbolSize=4, symbolBrush=symbol_brush, name="Intensity"
            )

        # Set title with improved styling
        self.hist_widget.setTitle("Intensity Histogram", color="#2c3e50", size="12pt")

        # Set default x-axis range: 0 to maximum value
        if all_x_data:
            x_max = max(all_x_data)
            self.hist_widget.setXRange(0, x_max, padding=0.02)

        # Set default y-axis range: 0 to maximum count (for histogram)
        if all_y_data:
            y_max = max(all_y_data)
            self.hist_widget.setYRange(0, y_max, padding=0.05)

        # Apply log scale if needed
        if hasattr(self, "hist_yscale") and self.hist_yscale == "log":
            self.hist_widget.setLogMode(y=True)
        else:
            self.hist_widget.setLogMode(y=False)

        # Apply manual ranges
        xmin, xmax, ymin, ymax = self.manual_ranges
        if xmin is not None or xmax is not None:
            self.hist_widget.setXRange(
                float(xmin) if xmin is not None else self.hist_widget.viewRange()[0][0],
                float(xmax) if xmax is not None else self.hist_widget.viewRange()[0][1],
            )
        if ymin is not None or ymax is not None:
            self.hist_widget.setYRange(
                float(ymin) if ymin is not None else self.hist_widget.viewRange()[1][0],
                float(ymax) if ymax is not None else self.hist_widget.viewRange()[1][1],
            )

        # Profile
        self.prof_widget.clear()
        self.last_profile_data = {}
        # Use same professional color palette as histogram
        colors = ["#e74c3c", "#2ecc71", "#3498db", "#34495e"]  # Red, Green, Blue, Dark gray

        # Store data for range calculation
        all_x_data = []
        all_y_data = []

        if arr.ndim == 3 and arr.shape[2] > 1:
            nch = arr.shape[2]
            if not self.channel_checks:
                self.channel_checks = [True] * nch
            for c in range(nch):
                prof = self._compute_profile(arr[:, :, c])
                if self.x_mode == "absolute" and self.image_rect is not None:
                    offset = self._get_profile_offset()
                    xs2 = np.arange(prof.size) + offset
                else:
                    xs2 = np.arange(prof.size)
                self.last_profile_data[f"C{c}"] = (xs2, prof)
                all_x_data.extend(xs2)
                all_y_data.extend(prof)
                if self.channel_checks[c]:
                    # Thicker line with small dots
                    pen = pg.mkPen(color=colors[c] if c < len(colors) else "#7f8c8d", width=3)
                    symbol_brush = pg.mkBrush(color=colors[c] if c < len(colors) else "#7f8c8d")
                    self.prof_widget.plot(
                        xs2, prof, pen=pen, symbol="o", symbolSize=4, symbolBrush=symbol_brush, name=f"C{c}"
                    )
        else:
            gray_data = arr if arr.ndim == 2 else arr[:, :, 0]
            prof = self._compute_profile(gray_data)
            if self.x_mode == "absolute" and self.image_rect is not None:
                offset = self._get_profile_offset()
                xs2 = np.arange(prof.size) + offset
            else:
                xs2 = np.arange(prof.size)
            self.last_profile_data["I"] = (xs2, prof)
            all_x_data.extend(xs2)
            all_y_data.extend(prof)
            # Thicker line with small dots
            pen = pg.mkPen(color="#34495e", width=3)
            symbol_brush = pg.mkBrush(color="#34495e")
            self.prof_widget.plot(
                xs2, prof, pen=pen, symbol="o", symbolSize=4, symbolBrush=symbol_brush, name="Intensity"
            )

        orientation_label = {"h": "Horizontal", "v": "Vertical", "d": "Diagonal"}[self.profile_orientation]
        mode_label = "Absolute" if self.x_mode == "absolute" else "Relative"
        # Set title with improved styling
        self.prof_widget.setTitle(f"Profile ({orientation_label}, {mode_label})", color="#2c3e50", size="12pt")
        self.prof_widget.setLabel("bottom", "Position" if self.x_mode == "relative" else "Absolute Position")
        self.prof_widget.setLabel("left", "Intensity")

        # Set default x-axis range: 0 to maximum value
        if all_x_data:
            x_max = max(all_x_data)
            x_min = min(all_x_data)
            # For profile, use 0 as minimum unless all values are greater than 0
            x_range_min = 0 if x_min >= 0 else x_min
            self.prof_widget.setXRange(x_range_min, x_max, padding=0.02)

        # Apply manual ranges
        if xmin is not None or xmax is not None:
            self.prof_widget.setXRange(
                float(xmin) if xmin is not None else self.prof_widget.viewRange()[0][0],
                float(xmax) if xmax is not None else self.prof_widget.viewRange()[0][1],
            )
        if ymin is not None or ymax is not None:
            self.prof_widget.setYRange(
                float(ymin) if ymin is not None else self.prof_widget.viewRange()[1][0],
                float(ymax) if ymax is not None else self.prof_widget.viewRange()[1][1],
            )

    def _update_metadata(self):
        """Update the metadata tab with image file information in table format."""
        if not hasattr(self, "metadata_table"):
            return

        if self.image_path is None or not self.image_path:
            self.metadata_table.setRowCount(1)
            self.metadata_table.setItem(0, 0, QTableWidgetItem("Error"))
            self.metadata_table.setItem(0, 1, QTableWidgetItem("No file path available"))
            return

        try:
            metadata = get_image_metadata(self.image_path)

            if not metadata:
                self.metadata_table.setRowCount(1)
                self.metadata_table.setItem(0, 0, QTableWidgetItem("Info"))
                self.metadata_table.setItem(0, 1, QTableWidgetItem("No metadata available"))
                return

            # Prepare data in order: Basic info first, then EXIF tags
            rows = []

            # 1. Basic information (from PIL)
            basic_keys = ["Filename", "Format", "Size", "Mode"]
            for key in basic_keys:
                if key in metadata:
                    value_str = str(metadata[key])
                    rows.append((key, value_str))

            # 2. EXIF tags (sorted alphabetically)
            exif_items = [(k, v) for k, v in metadata.items() if k not in basic_keys]
            for key, value in sorted(exif_items):
                value_str = str(value)
                rows.append((key, value_str))

            # Populate table
            self.metadata_table.setRowCount(len(rows))
            for i, (key, value) in enumerate(rows):
                self.metadata_table.setItem(i, 0, QTableWidgetItem(key))
                self.metadata_table.setItem(i, 1, QTableWidgetItem(value))

            # Store metadata for copying
            self.last_metadata = rows

        except Exception as e:
            self.metadata_table.setRowCount(1)
            self.metadata_table.setItem(0, 0, QTableWidgetItem("Error"))
            self.metadata_table.setItem(0, 1, QTableWidgetItem(f"Error reading metadata: {str(e)}"))
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
        keys = list(self.last_hist_data.keys())
        xs = self.last_hist_data[keys[0]][0]
        lines = [",".join(["x"] + keys)]
        for i in range(len(xs)):
            row = [str(xs[i])]
            for k in keys:
                row.append(str(int(self.last_hist_data[k][1][i])))
            lines.append(",".join(row))
        QGuiApplication.clipboard().setText("\n".join(lines))
        QMessageBox.information(self, "Copy", "Histogram copied to clipboard.")

    def copy_profile_to_clipboard(self):
        """Copy profile data as CSV to clipboard."""
        if not getattr(self, "last_profile_data", None):
            QMessageBox.information(self, "Copy", "No data.")
            return
        keys = list(self.last_profile_data.keys())
        xs = self.last_profile_data[keys[0]][0]
        lines = [",".join(["x"] + keys)]
        for i in range(len(xs)):
            row = [str(xs[i])]
            for k in keys:
                row.append(str(float(self.last_profile_data[k][1][i])))
            lines.append(",".join(row))
        QGuiApplication.clipboard().setText("\n".join(lines))
        QMessageBox.information(self, "Copy", "Profile copied to clipboard.")

    def _on_hist_click(self, event):
        """Handle histogram plot click events."""
        if event.double() and event.button() == 1:  # Left double-click
            if hasattr(self, "hist_yscale"):
                self.hist_yscale = "log" if self.hist_yscale == "linear" else "linear"
            else:
                self.hist_yscale = "log"
            self.update_contents()

    def _on_profile_click(self, event):
        """Handle profile plot click events.

        Left double-click: cycle through orientation modes (h → v → d → h)
        Right double-click: toggle x-axis mode (relative ↔ absolute)
        """
        if not event.double():
            return

        if event.button() == 1:  # Left double-click
            orientations = ["h", "v", "d"]
            current_idx = orientations.index(self.profile_orientation)
            self.profile_orientation = orientations[(current_idx + 1) % len(orientations)]
            self.update_contents()
        elif event.button() == 2:  # Right double-click
            self.x_mode = "absolute" if self.x_mode == "relative" else "relative"
            self.update_contents()

    def _compute_profile(self, channel_data: np.ndarray) -> np.ndarray:
        """Compute intensity profile for a single channel.

        Args:
            channel_data: 2D array (height x width) of pixel values

        Returns:
            1D array of averaged intensity values

        Orientation modes:
            "h": Horizontal - average along vertical axis (returns width-sized array)
            "v": Vertical - average along horizontal axis (returns height-sized array)
            "d": Diagonal - extract pixels along main diagonal (top-left to bottom-right)
        """
        if self.profile_orientation == "h":
            return channel_data.mean(axis=0)
        elif self.profile_orientation == "v":
            return channel_data.mean(axis=1)
        else:  # diagonal
            h, w = channel_data.shape
            diag_len = min(h, w)

            if h == w:
                # Square: simple diagonal extraction
                return np.diag(channel_data)
            else:
                # Rectangular: sample diagonal proportionally
                if diag_len <= 1:
                    return np.array([channel_data[0, 0]])

                y_coords = np.linspace(0, h - 1, diag_len).astype(int)
                x_coords = np.linspace(0, w - 1, diag_len).astype(int)
                return channel_data[y_coords, x_coords]

    def _get_profile_offset(self) -> int:
        """Get the offset for absolute x-axis mode.

        Returns:
            Offset value based on current orientation and image_rect
        """
        if self.image_rect is None:
            return 0

        if self.profile_orientation == "h":
            return self.image_rect.x()
        elif self.profile_orientation == "v":
            return self.image_rect.y()
        else:  # diagonal
            # For diagonal, use top-left corner as offset
            return min(self.image_rect.x(), self.image_rect.y())
