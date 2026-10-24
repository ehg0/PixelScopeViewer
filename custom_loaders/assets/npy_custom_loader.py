"""Example custom image loader for PixelScopeViewer.

This is an example demonstrating how to create a custom image loader
for file formats not natively supported by PixelScopeViewer.

To use this example:
1. Copy this file and rename it (e.g., my_loader.py)
2. Modify the loader function to handle your custom format
3. The loader will be automatically registered when the app starts

Note: You can disable this example loader by renaming it to start with
an underscore (e.g., _example_loader.py) or deleting it.
"""

from pathlib import Path

import numpy as np

# Import the registry to register our loader
from PixelScopeViewer.core.image_io import ImageLoaderRegistry


def npy_custom_loader(path: str) -> np.ndarray | None:
    ext = Path(path).suffix.lower()
    if ext not in [".npy"]:
        return None

    try:
        img = np.load(path)
        if img is None:
            raise RuntimeError(f"Cannot open image: {path}")

        # split RGGB channels
        if img.ndim == 2:
            img_r = img[0::2, 0::2]
            img_gr = img[0::2, 1::2]
            img_gb = img[1::2, 0::2]
            img_b = img[1::2, 1::2]
            return {"SRC": img, "R": img_r, "GR": img_gr, "GB": img_gb, "B": img_b}

        return img

    except Exception:
        # If loading fails, return None to try other loaders
        return None


# Register the loaders when this module is imported
# Higher priority values are tried first
registry = ImageLoaderRegistry.get_instance()

# Register specific format loaders with high priority
registry.register(npy_custom_loader, extensions=[".npy"], priority=10)


# Register wildcard fallback with low priority
# Uncomment the line below if you want to enable wildcard loading:
# registry.register(wildcard_fallback_loader, extensions=['*'], priority=-100)
