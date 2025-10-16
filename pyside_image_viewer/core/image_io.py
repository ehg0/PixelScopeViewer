"""Image I/O utilities for loading and converting images."""

import os
from typing import Optional
import numpy as np
from PIL import Image
from PySide6.QtGui import QImage


def numpy_to_qimage(arr: np.ndarray) -> QImage:
    if arr is None:
        return QImage()
    a = np.asarray(arr)
    if a.ndim == 2:
        disp = np.clip(a, 0, 255).astype(np.uint8)
        h, w = disp.shape
        return QImage(disp.data, w, h, w, QImage.Format_Grayscale8).copy()
    elif a.ndim == 3:
        h, w, c = a.shape
        disp = np.clip(a, 0, 255).astype(np.uint8)
        if c == 3:
            return QImage(disp.data, w, h, 3 * w, QImage.Format_RGB888).copy()
        elif c == 4:
            return QImage(disp.data, w, h, 4 * w, QImage.Format_RGBA8888).copy()
        else:
            gray = np.clip(a.mean(axis=2), 0, 255).astype(np.uint8)
            return QImage(gray.data, gray.shape[1], gray.shape[0], gray.shape[1], QImage.Format_Grayscale8).copy()
    else:
        raise ValueError("Unsupported array shape")


def pil_to_numpy(path: str) -> np.ndarray:
    img = Image.open(path)
    return np.array(img)


def is_image_file(path: str) -> bool:
    ext = os.path.splitext(path)[1].lower()
    return ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")
