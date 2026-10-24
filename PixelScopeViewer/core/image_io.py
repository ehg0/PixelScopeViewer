"""Image I/O utilities for loading and converting images.

This module provides functions for:
- Converting NumPy arrays to QImage for Qt display
- Loading images from files (OpenCV, OpenImageIO, NumPy)
- Validating image file extensions
- Extracting comprehensive image metadata
- Custom image loader registration (plugin system)

All functions handle edge cases gracefully and are UI-independent.
"""

import struct
from collections.abc import Callable
from pathlib import Path

import cv2
import numpy as np
import OpenImageIO as oiio
from PySide6.QtGui import QImage

from .metadata_utils import extract_exif, extract_png_metadata


class ImageLoaderRegistry:
    """Registry for custom image loaders (plugin system).

    This singleton class allows users to register custom loaders for
    image formats not natively supported by PixelScopeViewer.

    Custom loaders are tried before standard loaders, allowing users to
    override default behavior for specific extensions or handle completely
    new formats.

    Example:
        >>> def my_custom_loader(path: str) -> Optional[np.ndarray]:
        ...     if path.endswith('.myformat'):
        ...         # Custom loading logic
        ...         return np.load(path)
        ...     return None  # Cannot handle this file
        ...
        >>> registry = ImageLoaderRegistry.get_instance()
        >>> registry.register(my_custom_loader, extensions=['.myformat'], priority=10)
    """

    _instance = None

    @classmethod
    def get_instance(cls) -> "ImageLoaderRegistry":
        """Get the singleton instance of the registry."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        """Initialize the registry. Use get_instance() instead of direct instantiation."""
        self.custom_loaders = []

    def register(
        self,
        loader_func: Callable[[str], np.ndarray | None],
        extensions: list[str] | None = None,
        priority: int = 0,
    ):
        """Register a custom image loader.

        Args:
            loader_func: Function that takes a file path (str) and returns
                        a NumPy array, or None if it cannot handle the file.
                        Signature: (path: str) -> Optional[np.ndarray]
            extensions: List of file extensions this loader handles, e.g., ['.dat', '.custom'].
                       Use ['*'] or None to handle all extensions (wildcard).
            priority: Priority of this loader. Standard loaders have priority 0.
                     - priority > 0: Override standard loaders (e.g., custom .npy handler)
                     - priority = 0: Add new format support (default, does not override)
                     - priority < 0: Fallback loader (tried after all others fail)

                     Examples:
                     - priority = 1: Override .npy loading with custom logic
                     - priority = 0: Add support for .dat files (default)
                     - priority = -100: Wildcard fallback for any unknown format

        Note:
            - Loaders are tried in priority order (high to low)
            - Standard loaders (.npy, .exr, .png, etc.) have implicit priority 0
            - If a loader returns None, the next loader is tried
            - To override standard .npy loading, use priority >= 1
        """
        if extensions is None:
            extensions = ["*"]

        is_wildcard = "*" in extensions

        self.custom_loaders.append(
            {
                "func": loader_func,
                "extensions": [e.lower() for e in extensions] if not is_wildcard else ["*"],
                "priority": priority,
                "is_wildcard": is_wildcard,
            }
        )

        # Sort by priority (high to low)
        self.custom_loaders.sort(key=lambda x: x["priority"], reverse=True)

    def get_supported_extensions(self) -> tuple[list[str], bool]:
        """Get all supported extensions from custom loaders.

        Returns:
            (extensions, has_wildcard): Tuple of extension list and wildcard flag.
                extensions: List of registered extensions (e.g., ['.dat', '.custom'])
                has_wildcard: True if any wildcard loader is registered
        """
        exts = set()
        has_wildcard = False

        for loader_info in self.custom_loaders:
            if loader_info["is_wildcard"]:
                has_wildcard = True
            else:
                exts.update(loader_info["extensions"])

        return sorted(exts), has_wildcard

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
        # Ensure array is C-contiguous for QImage
        disp = np.ascontiguousarray(disp)
        return QImage(disp.data, w, h, w, QImage.Format_Grayscale8)
    elif a.ndim == 3:
        h, w, c = a.shape
        disp = np.clip(a, 0, 255).astype(np.uint8)
        # Ensure array is C-contiguous for QImage
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


def cv2_imread_unicode(path: str):
    data = np.fromfile(path, dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_UNCHANGED)


def read_bin(filename: Path, has_header: bool = True) -> np.ndarray:
    """Load 16-bit little-endian image data from a binary file.

    If a 4-byte header is present, it is interpreted as two unsigned
    16-bit integers (width, height) in little-endian order.

    Args:
        filename: Path to the binary image file.
        has_header: Whether the file includes a 4-byte (W, H) header.
            Defaults to ``True``.

    Returns:
        array: NumPy array of the image data (dtype: ``uint16``).

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If header dimensions do not match the data size.
    """
    with open(filename, "rb") as f:
        if has_header:
            header = f.read(4)
            width, height = struct.unpack("<HH", header)
            data = np.frombuffer(f.read(), dtype="<u2")
            img = data.reshape((height, width))
        else:
            data = np.frombuffer(f.read(), dtype="<u2")
            img = data
    return img


def load_image(path: str | Path) -> np.ndarray:
    """Load an image file into a NumPy array.

    Custom loaders registered via ImageLoaderRegistry are tried based on priority:
    - Priority > 0: Tried before standard loaders (can override default behavior)
    - Priority = 0: Tried after standard loaders (default for custom loaders)
    - Priority < 0: Tried as fallback after all other attempts fail

    Standard loaders have implicit priority of 0, so:
    - To override .npy loading: use priority >= 1
    - To add new formats without overriding: use priority = 0 (default)
    - For fallback/wildcard loaders: use priority < 0

    Supported inputs:
      - Custom formats: handled by registered custom loaders
      - .exr, .hdr: read with OpenImageIO; returns the image array with its
        original data type (often float32) and channel count from the file.
      - .npy: loaded via numpy.load and returned as-is.
      - other extensions: read with OpenCV; returns a NumPy array (typically
        uint8). Color images read by OpenCV are converted to RGB or RGBA
        (OpenCV's BGR/BGRA → RGB/RGBA). Grayscale images are returned as 2-D arrays.

    Args:
        path: Path to the image file (str or pathlib.Path).

    Returns:
        np.ndarray: Image data. dtype and channel order depend on the format
        (EXR/HDR may be float; LDR images are converted to RGB/RGBA uint8).

    Raises:
        RuntimeError: If OpenCV fails to open an LDR image.
        Exceptions from OpenImageIO or numpy.load may propagate for EXR/HDR/NPY.
    """
    path_str = str(path)
    ext = Path(path_str).suffix.lower()

    # Get custom loaders
    registry = ImageLoaderRegistry.get_instance()

    # Try high-priority custom loaders first (priority > 0)
    for loader_info in registry.custom_loaders:
        if loader_info["priority"] <= 0:
            break  # Loaders are sorted by priority, so we can stop here

        # Check if this loader handles this extension
        if loader_info["is_wildcard"] or ext in loader_info["extensions"]:
            try:
                result = loader_info["func"](path_str)
                if result is not None:
                    return result
            except Exception as e:
                print(f"Error: {e}")
                continue

    # Standard loaders (implicit priority = 0)
    # Read EXR / HDR files by OpenImageIO
    if ext in [".exr", ".hdr"]:
        img = oiio.ImageInput.open(str(path))
        arr = img.read_image()
        img.close()
        return arr
    elif ext == ".npy":
        arr = np.load(path)
        return arr
    elif ext == ".bin":
        arr = read_bin(path)
        return arr
    elif ext in [".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"]:
        # Read LDR image by OpenCV
        img = cv2_imread_unicode(path_str)
        if img is None:
            raise RuntimeError(f"Cannot open image: {path_str}")

        # Convert BGRA to RGBA
        if img.ndim == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGBA)
        # Convert BGR to RGB
        elif img.ndim == 3 and img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return img

    # Try normal-priority custom loaders (priority = 0)
    for loader_info in registry.custom_loaders:
        if loader_info["priority"] != 0:
            continue

        if loader_info["is_wildcard"] or ext in loader_info["extensions"]:
            try:
                result = loader_info["func"](path_str)
                if result is not None:
                    return result
            except Exception as e:
                print(f"Error: {e}")
                continue

    # Try low-priority/fallback custom loaders (priority < 0)
    for loader_info in registry.custom_loaders:
        if loader_info["priority"] >= 0:
            continue

        if loader_info["is_wildcard"] or ext in loader_info["extensions"]:
            try:
                result = loader_info["func"](path_str)
                if result is not None:
                    return result
            except Exception as e:
                print(f"Error: {e}")
                continue

    # No loader succeeded
    raise RuntimeError(f"Cannot open image: {path_str} (unsupported format)")


def is_image_file(path: str | Path) -> bool:
    """Return True if the given path has a supported image file suffix.

    This is a lightweight check that relies solely on the filename suffix
    (case-insensitive). It does not attempt to open the file.

    Custom loaders registered with ImageLoaderRegistry are also considered.

    Args:
        path: File path (string or Path-like).

    Returns:
        bool: True when suffix is supported (either standard or custom).
    """
    path_obj = Path(path)
    ext = path_obj.suffix.lower()

    # Standard extensions
    standard_exts = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".exr", ".npy", ".bin", ".hdr", ".gif", ".webp"}
    if ext in standard_exts:
        return True

    # Check custom loaders
    registry = ImageLoaderRegistry.get_instance()
    custom_exts, has_wildcard = registry.get_supported_extensions()

    # If wildcard loader exists, accept all files
    if has_wildcard:
        return True

    # Check if extension is registered
    return ext in custom_exts


def get_image_metadata(path: str | Path, arr: np.ndarray = None) -> dict:
    """Return a dictionary of image metadata.

    The function extracts basic image properties (format, size, dtype) and,
    when available, comprehensive EXIF tags using the ``exifread`` library.

    Args:
        path: Filesystem path (str/Path) to the image file
        arr: Numeric array-like image

    Returns:
        dict: Mapping of metadata keys to values. Basic keys include
        ``Filepath``, ``Format``, ``Size``, ``Mode`` and ``DataType``. If
        ``exifread`` is available and a path is provided, EXIF tags are
        included with spaces replaced by underscores in tag names.

    Behavior:
        - If the ``exifread`` package is not installed, the returned
          dictionary will include a ``Warning`` key advising installation.

    Example:
        >>> md = get_image_metadata('photo.jpg')
        >>> print(md['Format'], md.get('EXIF_DateTimeDigitized'))
    """
    metadata = {}

    # Extract basic information based on file type
    if path:
        path_obj = Path(path)

        # Add file size for all file types
        try:
            metadata["Filepath"] = str(path_obj.resolve())
            file_size = path_obj.stat().st_size
            if file_size < 1024:
                size_str = f"{file_size} B"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.1f} KB"
            elif file_size < 1024 * 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{file_size / (1024 * 1024 * 1024):.2f} GB"
            metadata["FileSize"] = size_str
        except Exception:
            pass

        ext = path_obj.suffix.lower()
        if ext in (".exr"):
            try:
                img = oiio.ImageInput.open(str(path_obj))
                spec = img.spec()
                metadata["Format"] = "EXR"
                metadata["Size"] = f"{spec.width} x {spec.height}"
                metadata["Channels"] = spec.nchannels
                metadata["DataType"] = str(spec.format).split()[-1]
                # Add additional metadata from spec
                if spec.get_string_attribute("compression"):
                    metadata["Compression"] = spec.get_string_attribute("compression")
                if spec.get_string_attribute("Software"):
                    metadata["Software"] = spec.get_string_attribute("Software")
                img.close()
            except Exception as e:
                metadata["Error"] = str(e)
        else:
            try:
                h, w = arr.shape[:2]
                metadata["Format"] = Path(path).suffix.lstrip(".").upper() or "Unknown"
                metadata["Size"] = f"{w} x {h}"
                metadata["DataType"] = str(arr.dtype)

                # Channels / Mode inference
                if arr.ndim == 2:
                    metadata["Channels"] = 1
                    metadata["Mode"] = "GRAY"
                else:
                    channels = arr.shape[2]
                    metadata["Channels"] = channels
                    if channels == 3:
                        metadata["Mode"] = "RGB"
                    elif channels == 4:
                        metadata["Mode"] = "RGBA"
                    else:
                        metadata["Mode"] = f"{channels}-channel"
            except Exception as e:
                metadata["Error (OpenCV)"] = str(e)

            try:
                exif_metadata = extract_exif(path_obj)
                for k, v in exif_metadata.items():
                    metadata[k] = v
            except Exception as e:
                metadata["Error (EXIF)"] = str(e)

            if ext in (".png"):
                try:
                    png_metadata = extract_png_metadata(path_obj)
                    for k, v in png_metadata.items():
                        metadata[k] = v
                except Exception as e:
                    metadata["Error (PNG chunks)"] = str(e)

    return metadata
