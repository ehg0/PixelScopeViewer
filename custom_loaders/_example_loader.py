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

import numpy as np
from pathlib import Path
from typing import Optional

# Import the registry to register our loader
from PixelScopeViewer.core.image_io import ImageLoaderRegistry


def npz_custom_loader(path: str) -> Optional[np.ndarray]:
    """Example loader for .npz files with custom structure.

    This example assumes .npz files contain a key named 'image_data'.
    Modify this function to match your specific file format.

    Args:
        path: Path to the file to load

    Returns:
        NumPy array if successfully loaded, None if cannot handle this file
    """
    # Only handle .npz files
    if not path.lower().endswith(".npz"):
        return None

    try:
        # Load the npz file
        data = np.load(path)

        # Check if it has our expected key
        if "image_data" in data:
            img = data["image_data"]

            # Optional: Apply any custom transformations
            # For example, if data is stored in a different shape:
            # img = img.reshape((height, width, channels))

            return img

        # If no 'image_data' key, try 'arr_0' (default numpy key)
        if "arr_0" in data:
            return data["arr_0"]

        # Cannot handle this npz file
        return None

    except Exception:
        # If loading fails, return None to try other loaders
        return None


def binary_custom_loader(path: str) -> Optional[np.ndarray]:
    """Example loader for raw binary image files.

    This example shows how to load custom binary formats where you know
    the dimensions and data type in advance.

    Modify the dimensions and dtype to match your format, or implement
    logic to read headers/metadata from the file.

    Args:
        path: Path to the file to load

    Returns:
        NumPy array if successfully loaded, None if cannot handle this file
    """
    # Only handle .dat or .raw files
    ext = Path(path).suffix.lower()
    if ext not in [".dat", ".raw"]:
        return None

    try:
        # Example: Fixed dimensions (modify as needed)
        # In practice, you might read dimensions from a header file
        # or parse them from the filename
        width = 512
        height = 512
        channels = 1
        dtype = np.uint8

        # Read the binary data
        with open(path, "rb") as f:
            data = np.fromfile(f, dtype=dtype)

        # Reshape to image dimensions
        expected_size = width * height * channels
        if len(data) != expected_size:
            # Size mismatch - cannot handle this file
            return None

        if channels == 1:
            img = data.reshape((height, width))
        else:
            img = data.reshape((height, width, channels))

        return img

    except Exception:
        return None


def wildcard_fallback_loader(path: str) -> Optional[np.ndarray]:
    """Example wildcard loader that tries to handle any file.

    This is a fallback loader that attempts various loading strategies.
    It will only be called if no extension-specific loader succeeds.

    Args:
        path: Path to the file to load

    Returns:
        NumPy array if successfully loaded, None if cannot handle this file
    """
    # Try loading as numpy pickle
    try:
        import pickle

        with open(path, "rb") as f:
            data = pickle.load(f)

        # Check if it's an array or dict with image data
        if isinstance(data, np.ndarray):
            return data
        elif isinstance(data, dict):
            # Look for common keys
            for key in ["image", "img", "data", "array"]:
                if key in data:
                    return data[key]
    except Exception:
        pass

    # Could not handle this file
    return None


# Register the loaders when this module is imported
# Higher priority values are tried first
registry = ImageLoaderRegistry.get_instance()

# Register specific format loaders with high priority
registry.register(npz_custom_loader, extensions=[".npz"], priority=10)
registry.register(binary_custom_loader, extensions=[".dat", ".raw"], priority=10)

# Register wildcard fallback with low priority
# Uncomment the line below if you want to enable wildcard loading:
# registry.register(wildcard_fallback_loader, extensions=['*'], priority=-100)

print("Example custom loaders registered (.npz, .dat, .raw)")
