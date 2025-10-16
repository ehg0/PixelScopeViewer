from typing import Optional
import numpy as np
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QTabWidget,
    QWidget,
    QHBoxLayout,
    QPushButton,
)
from PySide6.QtCore import QRect
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class AnalysisDialog(QDialog):
    def __init__(self, parent=None, image_array: Optional[np.ndarray] = None, image_rect: Optional[QRect] = None):
        super().__init__(parent)
        self.setWindowTitle("解析結果")
        self.resize(600, 400)
        self.image_array = image_array
        self.image_rect = image_rect

        layout = QVBoxLayout(self)
        self.info_label = QLabel()
        layout.addWidget(self.info_label)

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        # info tab
        info_tab = QWidget()
        info_layout = QVBoxLayout(info_tab)
        info_layout.addWidget(QLabel("選択領域情報"))
        self.tabs.addTab(info_tab, "Info")

        # histogram tab
        hist_tab = QWidget()
        hist_layout = QVBoxLayout(hist_tab)
        self.hist_fig = Figure(figsize=(5, 3))
        self.hist_canvas = FigureCanvas(self.hist_fig)
        hist_layout.addWidget(self.hist_canvas)
        self.tabs.addTab(hist_tab, "Histogram")

        # profile tab
        prof_tab = QWidget()
        prof_layout = QVBoxLayout(prof_tab)
        self.prof_fig = Figure(figsize=(5, 3))
        self.prof_canvas = FigureCanvas(self.prof_fig)
        prof_layout.addWidget(self.prof_canvas)
        self.tabs.addTab(prof_tab, "Profile")

        # close button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch(1)
        self.close_btn = QPushButton("閉じる")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)
        layout.addLayout(btn_layout)

        # profile display state
        self.profile_orientation = "h"  # 'h' horizontal (mean across rows), 'v' vertical (mean across cols)
        self.x_mode = "relative"  # 'relative' or 'absolute'

        if self.image_array is not None:
            self.update_contents()

        # histogram y-scale state
        self.hist_yscale = "linear"  # or 'log'

        # connect matplotlib click events to toggle modes (double-click)
        # left double-click on profile toggles orientation, right double-click toggles x-axis mode
        try:
            self.prof_cid = self.prof_canvas.mpl_connect("button_press_event", self._on_profile_click)
            self.hist_cid = self.hist_canvas.mpl_connect("button_press_event", self._on_hist_click)
        except Exception:
            # if mpl connection fails, silently ignore (non-interactive environments)
            self.prof_cid = None
            self.hist_cid = None

    def update_contents(self):
        arr = self.image_array
        # if image_rect is provided, crop to that region (image coords)
        if self.image_rect is not None:
            x, y, w, h = self.image_rect.x(), self.image_rect.y(), self.image_rect.width(), self.image_rect.height()
            arr = arr[y : y + h, x : x + w]

        # Info
        h, w = arr.shape[:2]
        self.info_label.setText(f"Size: {w} x {h}")

        # Histogram (grayscale if multi-channel)
        if arr.ndim == 3 and arr.shape[2] > 1:
            gray = (0.299 * arr[:, :, 0] + 0.587 * arr[:, :, 1] + 0.114 * arr[:, :, 2]).astype(np.uint8)
        else:
            gray = arr if arr.ndim == 2 else arr[:, :, 0]
        self.hist_fig.clear()
        ax = self.hist_fig.add_subplot(111)
        ax.hist(gray.ravel(), bins=256, range=(0, 255), color="black")
        ax.set_title("Intensity Histogram")
        # apply y-axis scale mode
        try:
            ax.set_yscale(self.hist_yscale)
        except Exception:
            pass
        self.hist_canvas.draw()

        # Profile: horizontal or vertical depending on mode
        self.prof_fig.clear()
        ax2 = self.prof_fig.add_subplot(111)

        if self.profile_orientation == "h":
            prof = gray.mean(axis=0)
            title = "Horizontal Profile (mean)"
        else:
            prof = gray.mean(axis=1)
            title = "Vertical Profile (mean)"

        # X axis: relative indices or absolute image coordinates (if image_rect provided)
        if self.x_mode == "absolute" and self.image_rect is not None:
            if self.profile_orientation == "h":
                start = int(self.image_rect.x())
            else:
                start = int(self.image_rect.y())
            xs = np.arange(start, start + prof.size)
            ax2.plot(xs, prof)
            ax2.set_xlabel("Absolute index")
        else:
            xs = np.arange(prof.size)
            ax2.plot(xs, prof)
            ax2.set_xlabel("Relative index")

        ax2.set_title(title)
        self.prof_canvas.draw()

    def _on_hist_click(self, event):
        # toggle y-axis linear <-> log on left double-click
        if not getattr(event, "dblclick", False):
            return
        # only react to left button double-click
        if getattr(event, "button", None) != 1:
            return
        # toggle
        self.hist_yscale = "log" if self.hist_yscale == "linear" else "linear"
        # update plot
        # If there's data currently plotted, just set yscale and redraw; easier to re-render full hist
        self.update_contents()

    def _on_profile_click(self, event):
        # Toggle modes on double-click
        if not getattr(event, "dblclick", False):
            return
        # event.button: 1 left, 3 right
        if getattr(event, "button", None) == 1:
            # left double-click: toggle orientation
            self.profile_orientation = "v" if self.profile_orientation == "h" else "h"
        elif getattr(event, "button", None) == 3:
            # right double-click: toggle x axis mode
            self.x_mode = "absolute" if self.x_mode == "relative" else "relative"
        else:
            # other buttons: toggle orientation as fallback
            self.profile_orientation = "v" if self.profile_orientation == "h" else "h"
        # refresh plots
        self.update_contents()
