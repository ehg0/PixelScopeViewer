"""Image I/O utilities for loading and converting images.

This module provides functions for:
- Converting NumPy arrays to QImage for Qt display
- Loading images from files using PIL
- Validating image file extensions
- Extracting comprehensive image metadata

All functions handle edge cases gracefully and are UI-independent.
"""

from pathlib import Path
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
from typing import Union, Tuple
import os
import sys
import numpy as np
from PIL import Image
from PySide6.QtGui import QImage

from .metadata_utils import is_binary_tag, is_printable_text, decode_bytes


def numpy_to_qimage(arr: np.ndarray) -> QImage:
    """Convert a NumPy image array to a Qt QImage suitable for display.

    This utility accepts common image array shapes and returns a copied
    QImage instance (detached from the original NumPy buffer) so the
    caller does not need to keep the NumPy array alive.

    Supported input shapes:
      - (H, W) -> 8-bit grayscale
      - (H, W, 3) -> RGB (8-bit per channel)
      - (H, W, 4) -> RGBA (8-bit per channel)
      - Any other channel count -> converted to grayscale by averaging

    Args:
        arr: Numeric array-like image. Values outside [0,255] are clipped.

    Returns:
        QImage: A freshly allocated QImage instance. If ``arr`` is ``None``
        an empty QImage is returned.

    Raises:
        ValueError: If ``arr`` has less than 2 dimensions.

    Example:
        >>> qimg = numpy_to_qimage(np.zeros((100, 200), dtype=np.uint8))
    """
    if arr is None:
        return QImage()
    a = np.asarray(arr)
    # Scale float images from [0,1] to [0,255]
    if np.issubdtype(a.dtype, np.floating):
        a = a * 255.0
    if a.ndim == 2:
        disp = np.clip(a, 0, 255).astype(np.uint8)
        h, w = disp.shape
        return QImage(disp.data, w, h, w, QImage.Format_Grayscale8).copy()
    elif a.ndim == 3:
        h, w, c = a.shape
        disp = np.clip(a, 0, 255).astype(np.uint8)
        # Ensure array is C-contiguous for QImage
        disp = np.ascontiguousarray(disp)
        if c == 3:
            return QImage(disp.data, w, h, 3 * w, QImage.Format_RGB888).copy()
        elif c == 4:
            return QImage(disp.data, w, h, 4 * w, QImage.Format_RGBA8888).copy()
        else:
            gray = np.clip(a.mean(axis=2), 0, 255).astype(np.uint8)
            return QImage(gray.data, gray.shape[1], gray.shape[0], gray.shape[1], QImage.Format_Grayscale8).copy()
    else:
        raise ValueError("Unsupported array shape")


def pil_to_numpy(path: Union[str, Path, Image.Image]) -> Tuple[np.ndarray, Image.Image]:
    """Load an image and return a NumPy array together with the PIL Image.

    This helper is a thin wrapper around Pillow's ``Image.open``. It is
    convenient when callers need both the NumPy pixel data for processing
    and the original PIL object for metadata extraction.

    Args:
        path: Path to the image file (``str`` or ``Path``), or an already
            opened ``PIL.Image.Image`` instance. If a PIL Image is passed,
            this function will still return a tuple ``(array, pil_image)``
            where ``pil_image`` is the same object.

    Returns:
        (array, pil_image):
            - array: NumPy array representation of the image (dtype depends
              on the source image).
            - pil_image: The PIL Image object (opened by this function if a
              path was given). For EXR and NPY files, pil_image will be None.

    Raises:
        PIL.UnidentifiedImageError: If the file cannot be opened as an image.
        FileNotFoundError: If a file path is provided but the file does not exist.

    Note:
        The returned NumPy array shares no required semantics with the
        QImage conversion helper; callers should copy or cast as needed.
    """
    if isinstance(path, Image.Image):
        img = path
        arr = np.array(img)
        return arr, img
    else:
        path_obj = Path(path)
        ext = path_obj.suffix.lower()
        if ext == ".exr":
            import OpenImageIO as oiio

            img = oiio.ImageInput.open(str(path))
            spec = img.spec()
            arr = img.read_image()
            img.close()
            return arr, None
        elif ext == ".npy":
            arr = np.load(path)
            return arr, None
        else:
            img = Image.open(path)
            arr = np.array(img)
            return arr, img


def is_image_file(path: Union[str, Path]) -> bool:
    """Return True if the given path has a supported image file suffix.

    This is a lightweight check that relies solely on the filename suffix
    (case-insensitive). It does not attempt to open the file.

    Args:
        path: File path (string or Path-like).

    Returns:
        bool: True when suffix is one of (.png, .jpg, .jpeg, .tif, .tiff, .bmp, .exr, .npy).
    """
    path_obj = Path(path)
    ext = path_obj.suffix.lower()
    return ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".exr", ".npy")


def get_image_metadata(path_or_img: Union[str, Path, Image.Image], pil_image: Image.Image = None) -> dict:
    """Return a dictionary of image metadata.

    The function tries to extract basic image properties using Pillow
    (format, size, mode) and, when a file path is available, attempts to
    read comprehensive EXIF tags using the ``exifread`` library.

    Args:
        path_or_img: Either a filesystem path (str/Path) to the image file
            or a ``PIL.Image.Image`` instance.
        pil_image: Deprecated alias for passing a PIL Image; provided for
            backward compatibility.

    Returns:
        dict: Mapping of metadata keys to values. Basic keys include
        ``Filepath``, ``Format``, ``Size``, ``Mode`` and ``DataType``. If
        ``exifread`` is available and a path is provided, EXIF tags are
        included with spaces replaced by underscores in tag names.

    Behavior:
        - If ``path_or_img`` is a PIL image, only basic properties are
          extracted (no disk EXIF parsing).
        - If the ``exifread`` package is not installed, the returned
          dictionary will include a ``Warning`` key advising installation.

    Example:
        >>> md = get_image_metadata('photo.jpg')
        >>> print(md['Format'], md.get('EXIF_DateTimeDigitized'))
    """
    metadata = {}

    # Handle deprecated pil_image parameter
    if pil_image is not None:
        img_obj = pil_image
        path = getattr(pil_image, "filename", None)
    elif isinstance(path_or_img, str):
        img_obj = None
        path = path_or_img
    else:
        # Assume it's a PIL Image object
        img_obj = path_or_img
        path = getattr(path_or_img, "filename", None)

    # Extract basic information based on file type
    if path:
        path_obj = Path(path)
        ext = path_obj.suffix.lower()
        if ext in (".exr", ".npy"):
            try:
                if ext == ".exr":
                    import OpenImageIO as oiio

                    img = oiio.ImageInput.open(str(path))
                    spec = img.spec()
                    metadata["Filepath"] = str(path_obj.resolve())
                    metadata["Format"] = "EXR"
                    metadata["Size"] = f"{spec.width} x {spec.height}"
                    metadata["DataType"] = str(spec.format)
                    metadata["Channels"] = spec.nchannels
                    # Add additional metadata from spec
                    if spec.get_string_attribute("compression"):
                        metadata["Compression"] = spec.get_string_attribute("compression")
                    if spec.get_string_attribute("Software"):
                        metadata["Software"] = spec.get_string_attribute("Software")
                    img.close()
                elif ext == ".npy":
                    arr = np.load(path)
                    metadata["Filepath"] = str(path_obj.resolve())
                    metadata["Format"] = "NPY"
                    if arr.ndim == 2:
                        metadata["Size"] = f"{arr.shape[1]} x {arr.shape[0]}"
                        metadata["Channels"] = 1
                    elif arr.ndim == 3:
                        metadata["Size"] = f"{arr.shape[1]} x {arr.shape[0]}"
                        metadata["Channels"] = arr.shape[2]
                    metadata["DataType"] = str(arr.dtype)
            except Exception as e:
                metadata["Error"] = str(e)
        else:
            # PIL-based images
            try:
                with Image.open(path) as img:
                    metadata["Filepath"] = str(Path(path).resolve())
                    metadata["Format"] = img.format or "Unknown"
                    metadata["Size"] = f"{img.size[0]} x {img.size[1]}"
                    metadata["DataType"] = str(np.array(img_obj).dtype)
                    metadata["Mode"] = img.mode
            except Exception as e:
                metadata["Error (PIL)"] = str(e)

    # Extract comprehensive EXIF data (only for PIL-supported formats)
    if isinstance(path_or_img, str) or (pil_image is not None and path):
        file_path = path if isinstance(path_or_img, str) else path
        if file_path and Path(file_path).suffix.lower() not in (".exr", ".npy"):
            try:
                import exifread

                with open(file_path, "rb") as f:
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
