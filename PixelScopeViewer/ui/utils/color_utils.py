"""Color utility functions for channel visualization.

This module provides common color schemes for multi-channel image display.
"""

from PySide6.QtGui import QColor
import numpy as np
import cv2


def get_default_channel_colors(n_channels: int) -> list:
    """Get default colors for n channels using hybrid scheme.

    Color scheme:
    - 1 channel: White (grayscale)
    - 3 channels: RGB (Red, Green, Blue)
    - 4 channels: RGBIR-like (Red, Green, Blue, Gray)
    - 5+ channels: Evenly distributed hues from color wheel

    Args:
        n_channels: Number of channels

    Returns:
        List of QColor objects

    Examples:
        >>> colors = get_default_channel_colors(3)
        >>> [c.name() for c in colors]
        ['#ff0000', '#00ff00', '#0000ff']

        >>> colors = get_default_channel_colors(8)
        >>> len(colors)
        8
    """
    # 1 channel: White
    if n_channels == 1:
        return [QColor(255, 255, 255)]

    # 2 channel : HSV色空間での色相を利用
    if n_channels == 2:
        # flow_x → red, flow_y → green
        return [
            QColor.fromHsv(0, 255, 255),  # hue 0° (red)
            QColor.fromHsv(120, 255, 255),  # hue 120° (green)
        ]

    # 3 channels: RGB
    if n_channels == 3:
        return [QColor(255, 0, 0), QColor(0, 255, 0), QColor(0, 0, 255)]

    # 4 channels: RGBIR-like
    if n_channels == 4:
        return [QColor(255, 0, 0), QColor(0, 255, 0), QColor(0, 0, 255), QColor(127, 127, 127)]

    # 5+ channels: Color wheel distribution
    colors = []
    for i in range(n_channels):
        hue = int(360 * i / n_channels)  # Evenly distribute hues
        color = QColor.fromHsv(hue, 200, 255)  # Moderate saturation for better visibility
        colors.append(color)
    return colors


def flow_to_hsv(flow: np.ndarray) -> np.ndarray:
    """2ch optical flow → 3ch HSV color map"""
    fx, fy = flow[..., 0], flow[..., 1]
    magnitude, angle = cv2.cartToPolar(fx, fy, angleInDegrees=True)

    # Hue: 方向 (0°〜360°)
    # Value: 大きさの正規化（0〜1 → 0〜255）
    hsv = np.zeros((*flow.shape[:2], 3), dtype=np.uint8)
    hsv[..., 0] = angle / 2  # OpenCVではHueが0〜180なので半分に
    hsv[..., 1] = 255  # Saturation固定
    hsv[..., 2] = cv2.normalize(magnitude, None, 0, 255, cv2.NORM_MINMAX)
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return bgr


if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget
    from PySide6.QtGui import QImage, QPixmap

    class FlowViewer(QMainWindow):
        def __init__(self, flow: np.ndarray):
            super().__init__()
            self.setWindowTitle("Optical Flow HSV Viewer")

            # Optical flow → BGR image
            color_img = flow_to_hsv(flow)

            # Convert to QImage
            h, w, ch = color_img.shape
            bytes_per_line = ch * w
            q_img = QImage(color_img.data, w, h, bytes_per_line, QImage.Format_BGR888)

            # Display
            label = QLabel()
            label.setPixmap(QPixmap.fromImage(q_img))

            central_widget = QWidget()
            layout = QVBoxLayout(central_widget)
            layout.addWidget(label)
            self.setCentralWidget(central_widget)

    def generate_dummy_flow(w=512, h=512):
        """テスト用: 円形のベクトルパターンを生成"""
        y, x = np.mgrid[0:h, 0:w]
        cx, cy = w / 2, h / 2
        fx = (x - cx) / w
        fy = (y - cy) / h
        return np.stack((fx, fy), axis=-1).astype(np.float32)

    app = QApplication(sys.argv)
    flow = generate_dummy_flow()  # ダミーのベクトル場

    # Save flow to a .npy file
    np.save("sample\\flow.npy", flow)
    print("Saved optical flow to sample\\flow.npy")

    viewer = FlowViewer(flow)
    viewer.resize(600, 600)
    viewer.show()
    sys.exit(app.exec())
