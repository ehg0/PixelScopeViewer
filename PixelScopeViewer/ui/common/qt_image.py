"""numpy 配列と Qt の画像の変換。"""

import numpy as np
from PySide6.QtGui import QImage


def numpy_to_qimage(arr: np.ndarray) -> QImage:
    """画像配列を表示用の 8bit QImage に変換する。

    float は [0, 1] を [0, 255] に scale し、範囲外は clip する。
    3ch は RGB、4ch は RGBA、それ以外の channel 数は平均して grayscale にする。

    Raises:
        ValueError: 配列の次元が 2 または 3 でない場合。
    """
    if arr is None:
        return QImage()
    a = np.asarray(arr)
    if np.issubdtype(a.dtype, np.floating):
        a = a * 255.0
    if a.ndim == 2:
        disp = np.clip(a, 0, 255).astype(np.uint8)
        h, w = disp.shape
        # QImage には C-contiguous な配列が必要
        disp = np.ascontiguousarray(disp)
        return QImage(disp.data, w, h, w, QImage.Format_Grayscale8)
    elif a.ndim == 3:
        h, w, c = a.shape
        disp = np.clip(a, 0, 255).astype(np.uint8)
        disp = np.ascontiguousarray(disp)
        if c == 3:
            return QImage(disp.data, w, h, 3 * w, QImage.Format_RGB888)
        elif c == 4:
            return QImage(disp.data, w, h, 4 * w, QImage.Format_RGBA8888)
        else:
            gray = np.clip(a.mean(axis=2), 0, 255).astype(np.uint8)
            gray = np.ascontiguousarray(gray)
            return QImage(gray.data, gray.shape[1], gray.shape[0], gray.shape[1], QImage.Format_Grayscale8)
    else:
        raise ValueError("Unsupported array shape")
