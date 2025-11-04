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
    """2ch optical flow → 3ch HSV color map

    Args:
        flow: 2-channel array (height, width, 2) with x and y components.
              Can be float or uint8.

    Returns:
        3-channel BGR image (uint8)
    """
    # Ensure float type for cv2.cartToPolar
    if flow.dtype != np.float32 and flow.dtype != np.float64:
        flow = flow.astype(np.float32)

    fx, fy = flow[..., 0], flow[..., 1]
    magnitude, angle = cv2.cartToPolar(fx, fy, angleInDegrees=True)

    # Hue: 方向 (0°〜360°)
    # Value: 大きさの正規化（0〜1 → 0〜255）
    # Hue: 方向 (0°〜360°)
    # Saturation: 固定で最大値
    # Value: 大きさ。NORM_MINMAXだとデータが小さい場合に暗くなるため、
    #        理論上の最大magnitude(sqrt(2)*255)を基準にスケーリング
    hsv = np.zeros((*flow.shape[:2], 3), dtype=np.uint8)
    hsv[..., 0] = np.clip(angle / 2, 0, 180).astype(np.uint8)  # Hue: 0〜180
    hsv[..., 1] = 255  # Saturation固定

    if False:
        # Valueはmagnitudeをロバスト正規化（上位パーセンタイルを最大基準に）
        # → 小さい動きでも可視化されやすく、全体が暗くなりにくい
        mag_max = float(np.percentile(magnitude, 99.0)) if magnitude.size > 0 else 0.0
        if mag_max <= 0.0:
            hsv[..., 2] = 0
        else:
            value = np.clip((magnitude / mag_max) * 255.0, 0, 255).astype(np.uint8)
            hsv[..., 2] = value
    if False:
        # Value の動的スケーリング ---
        # データの上位1%を基準に255スケーリング
        # → Viewerで明暗が適度に分かれ、低速も見やすい
        mag_max = float(np.percentile(magnitude, 99.0))
        if mag_max < 1e-6:
            hsv[..., 2] = 0
        else:
            hsv[..., 2] = np.clip((magnitude / mag_max) * 255.0, 0, 255).astype(np.uint8)

    if True:
        # Value: 固定スケール（max_magnitude基準）
        max_magnitude = 1.0
        hsv[..., 2] = np.clip((magnitude / max_magnitude) * 255.0, 0, 255).astype(np.uint8)

    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return bgr


def flow_to_hsv_rgb(flow: np.ndarray) -> np.ndarray:
    """2ch optical flow → 3ch RGB color image.

    Wrapper around ``flow_to_hsv`` that converts BGR to RGB for Qt display.
    """
    bgr = flow_to_hsv(flow)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return rgb


def apply_jet_colormap(gray: np.ndarray) -> np.ndarray:
    """Apply 'JET' colormap to a single-channel image and return RGB uint8.

    - Accepts float or integer arrays; values are normalized to [0, 255].
    - Returns an RGB image (height, width, 3) dtype uint8.
    """
    if gray is None:
        return None
    a = np.asarray(gray)
    if a.ndim == 3 and a.shape[2] == 1:
        a = a[..., 0]
    if a.ndim != 2:
        # Fallback: average across channels
        a = a.mean(axis=2) if a.ndim == 3 else a
    # Normalize to 0..255 uint8
    if np.issubdtype(a.dtype, np.floating):
        amin, amax = np.nanmin(a), np.nanmax(a)
        if amax > amin:
            norm = (a - amin) / (amax - amin)
        else:
            norm = np.zeros_like(a, dtype=np.float32)
        u8 = np.clip(norm * 255.0, 0, 255).astype(np.uint8)
    elif np.issubdtype(a.dtype, np.integer):
        try:
            max_val = np.iinfo(a.dtype).max
        except Exception:
            max_val = 255
        if max_val == 0:
            u8 = np.zeros_like(a, dtype=np.uint8)
        else:
            u8 = np.clip((a.astype(np.float32) / max_val) * 255.0, 0, 255).astype(np.uint8)
    else:
        u8 = np.clip(a, 0, 255).astype(np.uint8)
    # OpenCV colormap produces BGR
    bgr = cv2.applyColorMap(u8, cv2.COLORMAP_JET)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return rgb


def colorbar_jet(
    width: int = 256,
    height: int = 24,
    with_labels: bool = True,
    min_label: str | None = None,
    max_label: str | None = None,
) -> np.ndarray:
    """Generate a horizontal JET colorbar (RGB uint8).

    Optionally annotate with custom min/max labels.
    """
    grad = np.linspace(0, 255, width, dtype=np.uint8)
    bar = np.tile(grad[None, :], (height, 1))
    bgr = cv2.applyColorMap(bar, cv2.COLORMAP_JET)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    if with_labels:
        # Add simple 0 and 255 tick labels (or custom labels)
        rgb = rgb.copy()
        left_txt = min_label if min_label is not None else "0"
        right_txt = max_label if max_label is not None else "255"
        cv2.putText(rgb, left_txt, (2, height - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA)
        txt = right_txt
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        cv2.putText(
            rgb, txt, (width - tw - 2, height - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1, cv2.LINE_AA
        )
    return rgb


def colorbar_flow_hsv(width: int = 256, height: int = 256, with_labels: bool = True) -> np.ndarray:
    """Generate a circular HSV (hue) colorbar for flow angle visualization (RGB uint8).

    Instead of a linear bar, creates a circular hue wheel without numeric labels.
    The angle mapping matches generate_dummy_flow direction.
    """
    # Create a square canvas to fit a circle
    size = max(width, height)
    center = size / 2.0
    radius = 1.0

    # Create HSV image with circular gradient
    hsv = np.zeros((size, size, 3), dtype=np.uint8)

    # For each pixel, compute angle from center and set hue accordingly
    # Use the same coordinate system as generate_dummy_flow
    y, x = np.mgrid[:size, :size]
    dx = (x - center) / center  # Normalize like generate_dummy_flow
    dy = (y - center) / center

    # Distance from center (normalized)
    distance = np.sqrt(dx**2 + dy**2)

    # Angle in degrees (0-360), same as flow_to_hsv
    # cv2.cartToPolar returns angle in degrees when angleInDegrees=True
    magnitude, angle = cv2.cartToPolar(dx.astype(np.float32), dy.astype(np.float32), angleInDegrees=True)

    # Convert angle to OpenCV HSV hue range (0-180)
    hue = (angle / 2).astype(np.uint8)

    # Create circular mask (include pixels within radius)
    mask = distance <= radius

    # Set HSV values: full saturation and value inside circle, black outside
    hsv[mask, 0] = hue[mask]
    hsv[mask, 1] = 255
    # hsv[mask, 2] = 255
    hsv[mask, 2] = np.clip((magnitude[mask] / radius) * 255, 0, 255).astype(np.uint8)

    # Convert to BGR then RGB
    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    # Resize to requested dimensions if needed
    if size != width or size != height:
        rgb = cv2.resize(rgb, (width, height), interpolation=cv2.INTER_LINEAR)

    return rgb


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
        fx = (x - cx) / w * 2
        fy = (y - cy) / h * 2
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
