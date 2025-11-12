"""Multiframe expansion utility for 4D arrays.

This script pre-processes 4D NumPy arrays (H, W, C, N) and splits them
into separate frame files that can be loaded individually in PixelScopeViewer.

Usage:
    python expand_multiframe.py input.npy [output_dir]

Example:
    python expand_multiframe.py video_data.npy frames/
    
    This will create:
    - frames/frame_0000.npy
    - frames/frame_0001.npy
    - frames/frame_0002.npy
    - ...

Then open these files in PixelScopeViewer.
"""

import sys
import numpy as np
from pathlib import Path


def expand_multiframe(input_path: str, output_dir: str = None, prefix: str = "frame") -> int:
    """Expand a 4D array into separate frame files.
    
    Args:
        input_path: Path to the input .npy file containing 4D array
        output_dir: Directory to save frame files (default: same as input)
        prefix: Prefix for frame filenames (default: "frame")
    
    Returns:
        Number of frames created
    
    Raises:
        ValueError: If input is not a 4D array
        FileNotFoundError: If input file doesn't exist
    """
    input_path = Path(input_path)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    # Load the array
    print(f"Loading {input_path}...")
    data = np.load(input_path)
    
    # Validate dimensions
    if data.ndim != 4:
        raise ValueError(f"Expected 4D array, got {data.ndim}D array with shape {data.shape}")
    
    H, W, C, N = data.shape
    print(f"Array shape: (H={H}, W={W}, C={C}, Frames={N})")
    
    # Validate channel count
    if C not in [1, 2, 3, 4]:
        raise ValueError(f"Invalid channel count: {C}. Expected 1, 2, 3, or 4.")
    
    # Determine output directory
    if output_dir is None:
        output_dir = input_path.parent / f"{input_path.stem}_frames"
    else:
        output_dir = Path(output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}")
    
    # Calculate number of digits needed for frame numbering
    num_digits = len(str(N - 1))
    if num_digits < 4:
        num_digits = 4  # Use at least 4 digits
    
    # Extract and save each frame
    print(f"Extracting {N} frames...")
    for i in range(N):
        frame = data[:, :, :, i]
        output_path = output_dir / f"{prefix}_{i:0{num_digits}d}.npy"
        np.save(output_path, frame)
        
        # Progress indicator
        if (i + 1) % 10 == 0 or i == N - 1:
            print(f"  Progress: {i + 1}/{N} frames saved")
    
    print(f"\n✓ Successfully created {N} frame files")
    print(f"  Location: {output_dir.resolve()}")
    print(f"\nTo view in PixelScopeViewer:")
    print(f"  1. Open PixelScopeViewer")
    print(f"  2. Ctrl+O to open files")
    print(f"  3. Navigate to {output_dir}")
    print(f"  4. Select all frame files (Ctrl+A)")
    print(f"  5. Use 'n' and 'b' keys to navigate between frames")
    
    return N


def main():
    """Command-line interface."""
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nError: No input file specified")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        expand_multiframe(input_path, output_dir)
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
