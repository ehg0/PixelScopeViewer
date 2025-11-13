"""Example multiframe loader for 4D arrays (H, W, C, N).

This example demonstrates how to handle files containing multiple frames/images
in a single file, such as 4D NumPy arrays where N is the frame dimension.

The loader automatically splits the frames and loads them as separate images
in the viewer.
"""

import numpy as np
from pathlib import Path
from typing import Optional, List, Tuple
from PixelScopeViewer.core.image_io import ImageLoaderRegistry


def multiframe_npy_loader(path: str) -> Optional[np.ndarray]:
    """Load 4D .npy files (H, W, C, N) and return the first frame.

    This is a simplified example. For production use, you might want to:
    1. Store frame metadata in the image data dict
    2. Create a custom dialog to select which frames to load
    3. Implement frame caching for better performance

    Args:
        path: Path to the .npy file

    Returns:
        First frame as (H, W, C) array, or None if not a 4D array
    """
    if not path.lower().endswith(".npy"):
        return None

    try:
        data = np.load(path)

        # Check if it's a 4D array
        if data.ndim != 4:
            return None  # Let standard loader handle it

        H, W, C, N = data.shape

        # Validate dimensions
        if C not in [1, 2, 3, 4]:
            return None  # Invalid channel count

        # Return the first frame only
        # Note: This is a limitation of the current viewer design
        # which expects one array per file
        first_frame = data[:, :, :, 0]

        print(f"Loaded 4D array from {Path(path).name}: shape={data.shape}")
        print(f"  -> Returning first frame (0/{N-1})")
        print(f"  Tip: To load other frames, you would need to:")
        print(f"       1. Manually slice and save: data[:,:,:,i]")
        print(f"       2. Or implement a frame selection dialog")

        return first_frame

    except Exception as e:
        print(f"Error loading multiframe file: {e}")
        return None


# Alternative approach: Create virtual files for each frame
# This requires more complex implementation but provides better UX

_frame_cache = {}  # Cache loaded 4D arrays


def multiframe_expanded_loader(path: str) -> Optional[List[Tuple[str, np.ndarray]]]:
    """Load all frames from a 4D array and return as separate images.

    NOTE: This is a conceptual example. The current viewer API doesn't support
    returning multiple images from a single loader. You would need to extend
    the viewer's _add_images method to handle this.

    Args:
        path: Path to the .npy file

    Returns:
        List of (virtual_path, array) tuples for each frame
    """
    if not path.lower().endswith(".npy"):
        return None

    try:
        data = np.load(path)

        if data.ndim != 4:
            return None

        H, W, C, N = data.shape

        if C not in [1, 2, 3, 4]:
            return None

        # Create virtual paths and frames
        base_name = Path(path).stem
        frames = []

        for i in range(N):
            virtual_path = f"{path}#frame{i}"
            frame = data[:, :, :, i]
            frames.append((virtual_path, frame))

        print(f"Expanded {Path(path).name} into {N} frames")
        return frames

    except Exception:
        return None


# Register the loader
# Use priority=1 to override standard .npy loading
registry = ImageLoaderRegistry.get_instance()

# Simple approach: Load only first frame
registry.register(multiframe_npy_loader, extensions=[".npy"], priority=1)  # Override standard .npy loader

print("Multiframe loader registered (first frame only)")
print("Note: To load all frames, you need to manually extract them:")
print("  >>> data = np.load('file.npy')  # shape: (H, W, C, N)")
print("  >>> for i in range(data.shape[3]):")
print("  >>>     np.save(f'frame_{i}.npy', data[:,:,:,i])")
