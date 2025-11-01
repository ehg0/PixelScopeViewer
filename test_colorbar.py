"""Test script to verify circular HSV colorbar."""

import sys
import numpy as np
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtGui import QImage, QPixmap

# Add path to import from PixelScopeViewer
sys.path.insert(0, ".")

from PixelScopeViewer.ui.utils.color_utils import colorbar_flow_hsv


class ColorbarViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Circular HSV Colorbar Test")

        # Generate circular colorbar
        colorbar = colorbar_flow_hsv(width=256, height=256, with_labels=False)

        print(f"Colorbar shape: {colorbar.shape}")
        print(f"Colorbar dtype: {colorbar.dtype}")
        print(f"Colorbar range: [{colorbar.min()}, {colorbar.max()}]")

        # Convert to QImage
        h, w, ch = colorbar.shape
        bytes_per_line = ch * w
        q_img = QImage(colorbar.data, w, h, bytes_per_line, QImage.Format_RGB888)

        # Display
        label = QLabel()
        label.setPixmap(QPixmap.fromImage(q_img))

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.addWidget(label)
        self.setCentralWidget(central_widget)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = ColorbarViewer()
    viewer.resize(400, 400)
    viewer.show()
    sys.exit(app.exec())
