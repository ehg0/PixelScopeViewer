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

        if self.image_array is not None:
            self.update_contents()

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
        self.hist_canvas.draw()

        # Profile: show mean across rows (horizontal) as default
        self.prof_fig.clear()
        ax2 = self.prof_fig.add_subplot(111)
        # horizontal profile: mean across vertical dimension
        horiz = gray.mean(axis=0)
        ax2.plot(horiz)
        ax2.set_title("Horizontal Profile (mean)")
        self.prof_canvas.draw()
