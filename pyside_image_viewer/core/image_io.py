"""Image I/O utilities for loading and converting images.

This module provides functions for:
- Converting NumPy arrays to QImage for Qt display
- Loading images from files using PIL
- Validating image file extensions
- Extracting comprehensive image metadata

All functions handle edge cases gracefully and are UI-independent.
"""

import os
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
import numpy as np
from PIL import Image
from PySide6.QtGui import QImage

from .metadata_utils import is_binary_tag, is_printable_text, decode_bytes


def numpy_to_qimage(arr: np.ndarray) -> QImage:
    """Convert a NumPy array to QImage for Qt display.

    Args:
        arr: NumPy array with shape (H, W) for grayscale or (H, W, C) for color.
             Values should be in range [0, 255] or will be clipped.

    Returns:
        QImage ready for display in Qt widgets.
        Returns empty QImage if arr is None.

    Raises:
        ValueError: If array has unsupported shape (not 2D or 3D).

    Notes:
        - Grayscale: Format_Grayscale8
        - RGB: Format_RGB888 (3 channels)
        - RGBA: Format_RGBA8888 (4 channels)
        - Other channel counts: converted to grayscale by averaging
    """
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
    """Load an image from file path using PIL and convert to NumPy array.

    Args:
        path: File path to the image.

    Returns:
        NumPy array with shape (H, W) or (H, W, C).

    Raises:
        PIL.UnidentifiedImageError: If file cannot be opened as image.
        FileNotFoundError: If file does not exist.
    """
    img = Image.open(path)
    return np.array(img)


def is_image_file(path: str) -> bool:
    """Check if a file path has a supported image extension.

    Args:
        path: File path to check.

    Returns:
        True if extension is one of: .png, .jpg, .jpeg, .tif, .tiff, .bmp
        (case-insensitive).
    """
    ext = os.path.splitext(path)[1].lower()
    return ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp")


def get_image_metadata(path: str) -> dict:
    """Extract metadata from an image file using exifread for comprehensive EXIF data.

    Args:
        path: File path to the image.

    Returns:
        Dictionary containing image metadata including:
        - Basic info: format, size, mode (via PIL for image properties only)
        - Complete EXIF data (via exifread library)

    Notes:
        Returns empty dict if file cannot be opened or has no metadata.
        Uses exifread library for complete EXIF extraction.
    """
    metadata = {}

    # Extract basic PIL information
    try:
        with Image.open(path) as img:
            metadata["Format"] = img.format or "Unknown"
            metadata["Size"] = f"{img.size[0]} x {img.size[1]}"
            metadata["Mode"] = img.mode
            metadata["Filename"] = os.path.basename(path)
    except Exception as e:
        metadata["Error (PIL)"] = str(e)

    # Extract comprehensive EXIF data
    try:
        import exifread

        with open(path, "rb") as f:
            # Suppress exifread's debug messages
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                tags = exifread.process_file(f, details=False)

            for tag, value in tags.items():
                # Skip binary/thumbnail data
                if is_binary_tag(tag):
                    continue

                try:
                    value_str = str(value)

                    # Handle byte data with multiple encoding attempts
                    if isinstance(value.values, bytes):
                        # Skip large binary data
                        if len(value.values) > 1000:
                            continue

                        # Try decoding with multiple encodings
                        decoded = decode_bytes(value.values)
                        if not decoded:
                            continue
                        value_str = decoded

                    # Skip fields with excessive control characters
                    if not is_printable_text(value_str, min_ratio=0.8):
                        continue

                    # Store with cleaned tag name
                    clean_tag = tag.replace(" ", "_")
                    metadata[clean_tag] = value_str

                except Exception:
                    continue

    except ImportError:
        metadata["Warning"] = "exifread library not installed. Install with: pip install exifread"
    except Exception as e:
        metadata["Error (EXIF)"] = str(e)

    return metadata
