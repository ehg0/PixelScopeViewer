"""Analysis dialog module (single clean implementation).

This file provides a compact, stable AnalysisDialog plus small helper
dialogs (ChannelsDialog, RangesDialog). It is safe to import even when
matplotlib is not available; plotting functionality is disabled then.
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
    QCheckBox,
    QFormLayout,
    QLineEdit,
)
from PySide6.QtGui import QGuiApplication
from PySide6.QtCore import QRect

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    from matplotlib.ticker import AutoMinorLocator
except Exception:
    FigureCanvas = None
    Figure = None
    AutoMinorLocator = None


class ChannelsDialog(QDialog):
    def __init__(self, parent, nch: int, checks: Optional[list] = None):
        super().__init__(parent)
        self.setWindowTitle("Channels")
        self.setModal(True)
        layout = QVBoxLayout(self)
        self.checks: list[QCheckBox] = []
        for i in range(nch):
            cb = QCheckBox(f"C{i}")
            cb.setChecked(checks[i] if checks and i < len(checks) else True)
            layout.addWidget(cb)
            self.checks.append(cb)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def results(self) -> list[bool]:
        return [cb.isChecked() for cb in self.checks]


class RangesDialog(QDialog):
    def __init__(self, parent, xmin, xmax, ymin, ymax):
        super().__init__(parent)
        self.setWindowTitle("Axis ranges")
        self.setModal(True)
        layout = QFormLayout(self)
        self.xmin = QLineEdit()
        self.xmin.setText("" if xmin is None else str(xmin))
        self.xmax = QLineEdit()
        self.xmax.setText("" if xmax is None else str(xmax))
        self.ymin = QLineEdit()
        self.ymin.setText("" if ymin is None else str(ymin))
        self.ymax = QLineEdit()
        self.ymax.setText("" if ymax is None else str(ymax))
        layout.addRow("x min:", self.xmin)
        layout.addRow("x max:", self.xmax)
        layout.addRow("y min:", self.ymin)
        layout.addRow("y max:", self.ymax)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _parse(self, txt: str) -> Optional[float]:
        try:
            return float(txt) if txt is not None and txt != "" else None
        except Exception:
            return None

    def results(self) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        return (
            self._parse(self.xmin.text()),
            self._parse(self.xmax.text()),
            self._parse(self.ymin.text()),
            self._parse(self.ymax.text()),
        )


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

    def _on_hist_channels(self):
        if self.image_array is None:
            return
        nch = self.image_array.shape[2] if self.image_array.ndim == 3 else 1
        dlg = ChannelsDialog(self, nch, self.channel_checks)
        if dlg.exec() == QDialog.Accepted:
            self.channel_checks = dlg.results()
            self.update_contents()

    def _on_prof_channels(self):
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
                xs2 = np.arange(prof.size)
                self.last_profile_data[f"C{c}"] = (xs2, prof)
                if self.channel_checks[c]:
                    ax2.plot(xs2, prof, color=colors[c] if c < len(colors) else None, label=f"C{c}")
        else:
            prof = gray.mean(axis=0) if "gray" in locals() else arr.mean(axis=0)
            xs2 = np.arange(prof.size)
            self.last_profile_data["I"] = (xs2, prof)
            ax2.plot(xs2, prof, color="k", label="Intensity")

        ax2.set_title("Profile")
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
        if not getattr(event, "dblclick", False):
            return
        if getattr(event, "button", None) == 1:
            self.profile_orientation = "v" if self.profile_orientation == "h" else "h"
        elif getattr(event, "button", None) == 3:
            self.x_mode = "absolute" if self.x_mode == "relative" else "relative"
        self.update_contents()
