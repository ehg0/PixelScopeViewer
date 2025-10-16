"""Analysis dialog implementation (plots + info).

Compact, self-contained implementation that is safe to import when
matplotlib is not available. Provides Info / Histogram / Profile tabs
and simple double-click handlers for profile/histogram interactions.
"""

from typing import Optional, Tuple
import numpy as np

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QPushButton,
    QTextBrowser,
    QDialogButtonBox,
    QMessageBox,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QRect

from .controls import ChannelsDialog, RangesDialog

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    from matplotlib.ticker import AutoMinorLocator
except Exception:
    FigureCanvas = None
    Figure = None
    AutoMinorLocator = None


class AnalysisDialog(QDialog):
    def __init__(self, parent=None, image_array: Optional[np.ndarray] = None, image_rect: Optional[QRect] = None):
        super().__init__(parent)
        self.setWindowTitle("Analysis")
        self.resize(900, 600)
        self.image_array = image_array
        self.image_rect = image_rect

        # state
        self.profile_orientation = "h"
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

        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.rejected.connect(self.reject)
        box.accepted.connect(self.accept)
        main.addWidget(box)

    def set_image_and_rect(self, image_array: Optional[np.ndarray], image_rect: Optional[QRect]):
        self.image_array = image_array
        self.image_rect = image_rect
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
        arr = self.image_array
        if arr is None:
            self.info_browser.setPlainText("No data")
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
                prof = arr[:, :, c].mean(axis=0) if self.profile_orientation == "h" else arr[:, :, c].mean(axis=1)
                if self.x_mode == "absolute" and self.image_rect is not None:
                    # Absolute mode: offset x-axis by rect position
                    offset = self.image_rect.x() if self.profile_orientation == "h" else self.image_rect.y()
                    xs2 = np.arange(prof.size) + offset
                else:
                    # Relative mode: x-axis starts from 0
                    xs2 = np.arange(prof.size)
                self.last_profile_data[f"C{c}"] = (xs2, prof)
                if self.channel_checks[c]:
                    ax2.plot(xs2, prof, color=colors[c] if c < len(colors) else None, label=f"C{c}")
        else:
            # For grayscale or single-channel images
            gray_data = arr if arr.ndim == 2 else arr[:, :, 0]
            prof = gray_data.mean(axis=0) if self.profile_orientation == "h" else gray_data.mean(axis=1)
            if self.x_mode == "absolute" and self.image_rect is not None:
                offset = self.image_rect.x() if self.profile_orientation == "h" else self.image_rect.y()
                xs2 = np.arange(prof.size) + offset
            else:
                xs2 = np.arange(prof.size)
            self.last_profile_data["I"] = (xs2, prof)
            ax2.plot(xs2, prof, color="k", label="Intensity")

        # Set title with current orientation and mode
        orientation_label = "Horizontal" if self.profile_orientation == "h" else "Vertical"
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

    def copy_histogram_to_clipboard(self):
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
        if getattr(event, "dblclick", False) and getattr(event, "button", None) == 1:
            self.hist_yscale = "log" if self.hist_yscale == "linear" else "linear"
            self.update_contents()

    def _on_profile_click(self, event):
        import time

        # Try to get button from event
        btn = getattr(event, "button", None)

        # Check if matplotlib provides dblclick flag
        is_dblclick = getattr(event, "dblclick", False)

        # If no dblclick flag, use time-based detection
        if not is_dblclick and btn is not None:
            now = time.time()
            last_time = self._last_click_time.get(btn, 0)

            if now - last_time <= self._double_click_interval:
                # This is a double-click
                is_dblclick = True
                self._last_click_time[btn] = 0  # Reset
            else:
                # First click, record time
                self._last_click_time[btn] = now
                return

        # Handle double-click actions
        if is_dblclick:
            if btn == 1:  # Left double-click: toggle orientation
                self.profile_orientation = "v" if self.profile_orientation == "h" else "h"
                self.update_contents()
            elif btn == 3:  # Right double-click: toggle x-mode
                self.x_mode = "absolute" if self.x_mode == "relative" else "relative"
                self.update_contents()
