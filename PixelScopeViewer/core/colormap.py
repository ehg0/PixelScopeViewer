"""optical flow と JET の colormap・colorbar の生成（Qt 非依存）。"""

import cv2
import numpy as np


def flow_to_hsv(flow: np.ndarray) -> np.ndarray:
    """2ch の optical flow を、向きを hue・大きさを value とした BGR 画像（uint8）に変換する。"""
    # cv2.cartToPolar は float が必要
    if flow.dtype != np.float32 and flow.dtype != np.float64:
        flow = flow.astype(np.float32)

    fx, fy = flow[..., 0], flow[..., 1]
    magnitude, angle = cv2.cartToPolar(fx, fy, angleInDegrees=True)

    hsv = np.zeros((*flow.shape[:2], 3), dtype=np.uint8)
    hsv[..., 0] = np.clip(angle / 2, 0, 180).astype(np.uint8)  # OpenCV の hue は 0〜180
    hsv[..., 1] = 255  # saturation は固定

    # value は固定の最大値で scale する（NORM_MINMAX だと小さい動きの画像が暗くなるため）
    max_magnitude = 1.0
    hsv[..., 2] = np.clip((magnitude / max_magnitude) * 255.0, 0, 255).astype(np.uint8)

    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    return bgr


def flow_to_hsv_rgb(flow: np.ndarray) -> np.ndarray:
    """2ch の optical flow を Qt 表示用の RGB 画像に変換する。"""
    bgr = flow_to_hsv(flow)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return rgb


def apply_jet_colormap(gray: np.ndarray) -> np.ndarray:
    """1ch 画像を [0, 255] に正規化して JET colormap を適用し、RGB の uint8 画像を返す。"""
    if gray is None:
        return None
    a = np.asarray(gray)
    if a.ndim == 3 and a.shape[2] == 1:
        a = a[..., 0]
    if a.ndim != 2:
        # 多 channel の場合は平均する
        a = a.mean(axis=2) if a.ndim == 3 else a
    if np.issubdtype(a.dtype, np.floating):
        amin, amax = np.nanmin(a), np.nanmax(a)
        norm = (a - amin) / (amax - amin) if amax > amin else np.zeros_like(a, dtype=np.float32)
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
    # OpenCV の colormap は BGR で出力される
    bgr = cv2.applyColorMap(u8, cv2.COLORMAP_JET)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    return rgb


def colorbar_jet(
    width: int = 256,
    height: int = 24,
    with_labels: bool = True,
    min_label: str | None = None,
    max_label: str | None = None,
    label_rgb: tuple[int, int, int] = (255, 255, 255),
) -> np.ndarray:
    """横向きの JET colorbar（RGB の uint8 画像）を生成する。

    Args:
        width: 幅。
        height: 高さ。
        with_labels: 両端に label を描画するか。
        min_label: 左端の label。None の場合は "0"。
        max_label: 右端の label。None の場合は "255"。
        label_rgb: label の色。
    """
    grad = np.linspace(0, 255, width, dtype=np.uint8)
    bar = np.tile(grad[None, :], (height, 1))
    bgr = cv2.applyColorMap(bar, cv2.COLORMAP_JET)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    if with_labels:
        rgb = rgb.copy()
        left_txt = min_label if min_label is not None else "0"
        right_txt = max_label if max_label is not None else "255"
        cv2.putText(rgb, left_txt, (2, height - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.4, label_rgb, 1, cv2.LINE_AA)
        txt = right_txt
        (tw, th), _ = cv2.getTextSize(txt, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
        cv2.putText(
            rgb,
            txt,
            (width - tw - 2, height - 6),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            label_rgb,
            1,
            cv2.LINE_AA,
        )
    return rgb


def colorbar_flow_hsv(width: int = 256, height: int = 256, with_labels: bool = True) -> np.ndarray:
    """optical flow の向きを示す円形の hue wheel（RGB の uint8 画像）を生成する。"""
    size = max(width, height)
    center = size / 2.0
    radius = 1.0

    hsv = np.zeros((size, size, 3), dtype=np.uint8)

    # 中心からの正規化座標
    y, x = np.mgrid[:size, :size]
    dx = (x - center) / center
    dy = (y - center) / center

    distance = np.sqrt(dx**2 + dy**2)

    # flow_to_hsv と同じく角度（度）を hue に対応させる
    magnitude, angle = cv2.cartToPolar(dx.astype(np.float32), dy.astype(np.float32), angleInDegrees=True)

    # OpenCV の hue の範囲（0〜180）に変換する
    hue = (angle / 2).astype(np.uint8)

    mask = distance <= radius

    # 円の内側のみ色を付け、外側は黒にする
    hsv[mask, 0] = hue[mask]
    hsv[mask, 1] = 255
    hsv[mask, 2] = np.clip((magnitude[mask] / radius) * 255, 0, 255).astype(np.uint8)

    bgr = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

    if size != width or size != height:
        rgb = cv2.resize(rgb, (width, height), interpolation=cv2.INTER_LINEAR)

    return rgb
