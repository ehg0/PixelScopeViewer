"""Production-ready multiframe loader with automatic frame expansion.

This loader handles 4D arrays (H, W, C, N) by automatically creating
separate images for each frame in the viewer.

Usage:
1. Copy this file and remove the leading underscore to enable it
2. Load a .npy file with 4D array
3. All frames will be loaded as separate images automatically
"""

import numpy as np
from pathlib import Path
from typing import Optional


# Global cache to store multiframe data
_multiframe_registry = {}


def load_multiframe_npy(path: str) -> Optional[np.ndarray]:
    """Load 4D .npy files and register them for frame expansion.
    
    This loader works in conjunction with the viewer to automatically
    expand 4D arrays into separate frames.
    
    Args:
        path: Path to the .npy file
    
    Returns:
        First frame if 4D array, None otherwise
    """
    if not path.lower().endswith('.npy'):
        return None
    
    try:
        data = np.load(path)
        
        # Only handle 4D arrays
        if data.ndim != 4:
            return None  # Let standard loader handle 2D/3D arrays
        
        H, W, C, N = data.shape
        
        # Validate channel count
        if C not in [1, 2, 3, 4]:
            print(f"Warning: Invalid channel count {C} in {Path(path).name}")
            return None
        
        # Store the full data in registry for frame expansion
        _multiframe_registry[path] = data
        
        # Return first frame
        first_frame = data[:, :, :, 0]
        
        print(f"Loaded 4D array: {Path(path).name}")
        print(f"  Shape: {data.shape} (H={H}, W={W}, C={C}, Frames={N})")
        print(f"  -> Will expand into {N} separate images")
        
        return first_frame
        
    except Exception as e:
        print(f"Error loading {path}: {e}")
        return None


def get_multiframe_count(path: str) -> int:
    """Get the number of frames in a multiframe file.
    
    Args:
        path: Original file path
    
    Returns:
        Number of frames, or 0 if not a multiframe file
    """
    if path in _multiframe_registry:
        data = _multiframe_registry[path]
        return data.shape[3]  # N dimension
    return 0


def get_multiframe_frame(path: str, frame_index: int) -> Optional[np.ndarray]:
    """Get a specific frame from a multiframe file.
    
    Args:
        path: Original file path
        frame_index: Frame index (0-based)
    
    Returns:
        Frame array (H, W, C) or None if not available
    """
    if path not in _multiframe_registry:
        return None
    
    data = _multiframe_registry[path]
    N = data.shape[3]
    
    if frame_index < 0 or frame_index >= N:
        return None
    
    return data[:, :, :, frame_index]


# Register the loader with high priority to override standard .npy loading
from PixelScopeViewer.core.image_io import ImageLoaderRegistry

registry = ImageLoaderRegistry.get_instance()
registry.register(
    load_multiframe_npy,
    extensions=['.npy'],
    priority=1  # Override standard .npy loader for 4D arrays
)

print("Multiframe loader registered (.npy with 4D arrays)")
print("Note: 4D arrays will show only the first frame.")
print("To load all frames, you need to:")
print("  1. Save each frame separately, or")
print("  2. Extend the viewer to call get_multiframe_frame() for each frame")
