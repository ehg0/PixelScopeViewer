"""Analysis dialog with tabbed interface for image analysis.

This module provides the main AnalysisDialog which displays:
- Info tab: Selection size and position
- Histogram tab: Intensity histogram with logarithmic scale toggle
- Profile tab: Line profile (horizontal/vertical) with absolute/relative modes

The dialog supports matplotlib-based interactive plots with double-click
gestures for toggling plot modes. If matplotlib is not available, the
histogram and profile tabs will show empty placeholders.

Dependencies:
    - matplotlib (optional): For histogram and profile plotting
    - numpy: For data processing
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
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.ticker import AutoMinorLocator
except ImportError:
    Figure = None
    FigureCanvas = None
    AutoMinorLocator = None

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
        Requires matplotlib for histogram and profile plots. If matplotlib
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
            if hasattr(self, "hist_canvas") and self.hist_canvas is not None:
                self.hist_canvas.mpl_connect("button_press_event", self._on_hist_click)
            if hasattr(self, "prof_canvas") and self.prof_canvas is not None:
                self.prof_canvas.mpl_connect("button_press_event", self._on_profile_click)
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
        if Figure is not None:
            self.prof_fig = Figure(figsize=(5, 3))
            self.prof_canvas = FigureCanvas(self.prof_fig)
            pl.addWidget(self.prof_canvas, 1)
        else:
            self.prof_fig = None
            self.prof_canvas = None
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
        if Figure is not None:
            self.hist_fig = Figure(figsize=(5, 3))
            self.hist_canvas = FigureCanvas(self.hist_fig)
            hl.addWidget(self.hist_canvas, 1)
        else:
            self.hist_fig = None
            self.hist_canvas = None

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
        dlg = ChannelsDialog(self, nch, self.channel_checks)
        if dlg.exec() == QDialog.Accepted:
            self.channel_checks = dlg.results()
            self.update_contents()

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

        if self.hist_fig is None:
            return

        # Histogram
        self.hist_fig.clear()
        ax = self.hist_fig.add_subplot(111)
        self.last_hist_data = {}
        colors = ["r", "g", "b", "k"]
        if arr.ndim == 3 and arr.shape[2] > 1:
            nch = arr.shape[2]
            if not self.channel_checks:
                self.channel_checks = [True] * nch
            for c in range(nch):
                data = arr[:, :, c].ravel()
                hist, bins = np.histogram(data, bins=256, range=(0, 255))
                xs = (bins[:-1] + bins[1:]) / 2.0
                self.last_hist_data[f"C{c}"] = (xs, hist)
                if self.channel_checks[c]:
                    ax.plot(xs, hist, color=colors[c] if c < len(colors) else None, label=f"C{c}")
        else:
            gray = arr if arr.ndim == 2 else arr[:, :, 0]
            hist, bins = np.histogram(gray.ravel(), bins=256, range=(0, 255))
            xs = (bins[:-1] + bins[1:]) / 2.0
            self.last_hist_data["I"] = (xs, hist)
            ax.plot(xs, hist, color="k", label="Intensity")

        ax.set_title("Intensity Histogram")
        try:
            if AutoMinorLocator is not None:
                ax.xaxis.set_minor_locator(AutoMinorLocator())
                ax.yaxis.set_minor_locator(AutoMinorLocator())
            ax.grid(which="major", linestyle="-", color="gray", linewidth=0.6)
            ax.grid(which="minor", linestyle=":", color="lightgray", linewidth=0.4)
        except Exception:
            pass
        try:
            ax.set_yscale(self.hist_yscale)
        except Exception:
            pass
        if ax.get_legend():
            ax.legend()
        xmin, xmax, ymin, ymax = self.manual_ranges
        try:
            if xmin is not None:
                ax.set_xlim(left=float(xmin))
            if xmax is not None:
                ax.set_xlim(right=float(xmax))
            if ymin is not None:
                ax.set_ylim(bottom=float(ymin))
            if ymax is not None:
                ax.set_ylim(top=float(ymax))
        except Exception:
            pass
        try:
            self.hist_canvas.draw()
        except Exception:
            pass

        # Profile
        self.prof_fig.clear()
        ax2 = self.prof_fig.add_subplot(111)
        self.last_profile_data = {}
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
                if self.channel_checks[c]:
                    ax2.plot(xs2, prof, color=colors[c] if c < len(colors) else None, label=f"C{c}")
        else:
            gray_data = arr if arr.ndim == 2 else arr[:, :, 0]
            prof = self._compute_profile(gray_data)
            if self.x_mode == "absolute" and self.image_rect is not None:
                offset = self._get_profile_offset()
                xs2 = np.arange(prof.size) + offset
            else:
                xs2 = np.arange(prof.size)
            self.last_profile_data["I"] = (xs2, prof)
            ax2.plot(xs2, prof, color="k", label="Intensity")

        orientation_label = {"h": "Horizontal", "v": "Vertical", "d": "Diagonal"}[self.profile_orientation]
        mode_label = "Absolute" if self.x_mode == "absolute" else "Relative"
        ax2.set_title(f"Profile ({orientation_label}, {mode_label})")
        ax2.set_xlabel("Position" if self.x_mode == "relative" else "Absolute Position")
        ax2.set_ylabel("Intensity")
        try:
            if AutoMinorLocator is not None:
                ax2.xaxis.set_minor_locator(AutoMinorLocator())
                ax2.yaxis.set_minor_locator(AutoMinorLocator())
            ax2.grid(which="major", linestyle="-", color="gray", linewidth=0.6)
            ax2.grid(which="minor", linestyle=":", color="lightgray", linewidth=0.4)
        except Exception:
            pass
        try:
            if xmin is not None:
                ax2.set_xlim(left=float(xmin))
            if xmax is not None:
                ax2.set_xlim(right=float(xmax))
            if ymin is not None:
                ax2.set_ylim(bottom=float(ymin))
            if ymax is not None:
                ax2.set_ylim(top=float(ymax))
        except Exception:
            pass
        if ax2.get_legend():
            ax2.legend()
        try:
            self.prof_canvas.draw()
        except Exception:
            pass

        # Update metadata tab
        self._update_metadata()

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
        if getattr(event, "dblclick", False) and getattr(event, "button", None) == 1:
            self.hist_yscale = "log" if self.hist_yscale == "linear" else "linear"
            self.update_contents()

    def _on_profile_click(self, event):
        """Handle profile plot click events with time-based double-click fallback.

        Left double-click: cycle through orientation modes (h → v → d → h)
        Right double-click: toggle x-axis mode (relative ↔ absolute)
        """
        import time

        btn = getattr(event, "button", None)
        is_dblclick = getattr(event, "dblclick", False)

        # Fallback: time-based double-click detection
        if not is_dblclick and btn is not None:
            now = time.time()
            last_time = self._last_click_time.get(btn, 0)

            if now - last_time <= self._double_click_interval:
                is_dblclick = True
                self._last_click_time[btn] = 0
            else:
                self._last_click_time[btn] = now
                return

        if is_dblclick:
            if btn == 1:  # Left: cycle orientation h → v → d → h
                if self.profile_orientation == "h":
                    self.profile_orientation = "v"
                elif self.profile_orientation == "v":
                    self.profile_orientation = "d"
                else:
                    self.profile_orientation = "h"
                self.update_contents()
            elif btn == 3:  # Right: toggle x-mode
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
            "d": Diagonal - extract pixels along main diagonal (top-left to bottom-right),
                 average perpendicular pixels when array is not square
        """
        if self.profile_orientation == "h":
            return channel_data.mean(axis=0)
        elif self.profile_orientation == "v":
            return channel_data.mean(axis=1)
        else:  # diagonal
            h, w = channel_data.shape
            diag_len = min(h, w)

            # Extract diagonal pixels (top-left to bottom-right)
            # For non-square images, sample along the diagonal of the smaller dimension
            if h == w:
                # Square: simple diagonal extraction
                prof = np.array([channel_data[i, i] for i in range(diag_len)])
            else:
                # Rectangular: sample diagonal proportionally
                prof = []
                for i in range(diag_len):
                    # Calculate corresponding coordinates in larger dimension
                    y = int(i * (h - 1) / (diag_len - 1)) if diag_len > 1 else 0
                    x = int(i * (w - 1) / (diag_len - 1)) if diag_len > 1 else 0
                    prof.append(channel_data[y, x])
                prof = np.array(prof)

            return prof

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
