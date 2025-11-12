"""Generate sample 4D array files for testing multiframe functionality.

This script creates various test cases of 4D NumPy arrays to demonstrate
the expand_multiframe.py utility.
"""

import numpy as np
from pathlib import Path


def create_sample_video_frames(output_path: str = "sample_video.npy", num_frames: int = 30):
    """Create a sample video with moving gradient pattern.
    
    Args:
        output_path: Path to save the 4D array
        num_frames: Number of frames to generate
    """
    H, W, C = 256, 256, 3
    
    print(f"Creating sample video with {num_frames} frames...")
    data = np.zeros((H, W, C, num_frames), dtype=np.uint8)
    
    for i in range(num_frames):
        # Create a moving gradient pattern
        t = i / num_frames
        
        # Red channel: horizontal gradient
        for x in range(W):
            data[:, x, 0, i] = int(255 * (x / W) * (1 - t))
        
        # Green channel: vertical gradient
        for y in range(H):
            data[y, :, 1, i] = int(255 * (y / H) * t)
        
        # Blue channel: diagonal pattern
        for y in range(H):
            for x in range(W):
                data[y, x, 2, i] = int(255 * ((x + y) / (W + H)) * (0.5 + 0.5 * np.sin(t * 2 * np.pi)))
    
    np.save(output_path, data)
    print(f"✓ Saved: {output_path}")
    print(f"  Shape: {data.shape} (H={H}, W={W}, C={C}, Frames={num_frames})")
    print(f"  Size: {Path(output_path).stat().st_size / 1024 / 1024:.2f} MB")
    return output_path


def create_sample_grayscale_sequence(output_path: str = "sample_sequence.npy", num_frames: int = 20):
    """Create a grayscale image sequence with brightness variation.
    
    Args:
        output_path: Path to save the 4D array
        num_frames: Number of frames to generate
    """
    H, W, C = 128, 128, 1
    
    print(f"Creating grayscale sequence with {num_frames} frames...")
    data = np.zeros((H, W, C, num_frames), dtype=np.uint8)
    
    for i in range(num_frames):
        # Create concentric circles with varying brightness
        t = i / num_frames
        center_x, center_y = W // 2, H // 2
        
        for y in range(H):
            for x in range(W):
                dx = x - center_x
                dy = y - center_y
                distance = np.sqrt(dx**2 + dy**2)
                
                # Ripple pattern
                value = np.sin(distance * 0.1 - t * 2 * np.pi * 3) * 127 + 127
                data[y, x, 0, i] = int(np.clip(value, 0, 255))
    
    np.save(output_path, data)
    print(f"✓ Saved: {output_path}")
    print(f"  Shape: {data.shape} (H={H}, W={W}, C={C}, Frames={num_frames})")
    print(f"  Size: {Path(output_path).stat().st_size / 1024 / 1024:.2f} MB")
    return output_path


def create_sample_large_video(output_path: str = "sample_large_video.npy", num_frames: int = 100):
    """Create a larger sample video for performance testing.
    
    Args:
        output_path: Path to save the 4D array
        num_frames: Number of frames to generate
    """
    H, W, C = 512, 512, 3
    
    print(f"Creating large video with {num_frames} frames...")
    print("  (This may take a moment...)")
    
    data = np.zeros((H, W, C, num_frames), dtype=np.uint8)
    
    for i in range(num_frames):
        # Progress indicator
        if (i + 1) % 10 == 0:
            print(f"  Progress: {i + 1}/{num_frames} frames")
        
        # Simple noise pattern with time variation
        t = i / num_frames
        noise = np.random.randint(0, 256, (H, W, C), dtype=np.uint8)
        
        # Add some structure
        for c in range(C):
            # Blend with gradient
            gradient = np.linspace(0, 255 * t, W, dtype=np.uint8)
            gradient_2d = np.tile(gradient, (H, 1))
            data[:, :, c, i] = (noise[:, :, c] * 0.5 + gradient_2d * 0.5).astype(np.uint8)
    
    np.save(output_path, data)
    print(f"✓ Saved: {output_path}")
    print(f"  Shape: {data.shape} (H={H}, W={W}, C={C}, Frames={num_frames})")
    print(f"  Size: {Path(output_path).stat().st_size / 1024 / 1024:.2f} MB")
    return output_path


def main():
    """Generate all sample files."""
    print("=" * 60)
    print("Generating Sample 4D Array Files")
    print("=" * 60)
    print()
    
    # Create sample directory
    sample_dir = Path("sample")
    sample_dir.mkdir(exist_ok=True)
    
    # Generate samples
    samples = []
    
    print("[1/3] Video with gradient pattern")
    samples.append(create_sample_video_frames(str(sample_dir / "sample_video.npy"), num_frames=30))
    print()
    
    print("[2/3] Grayscale sequence with ripple")
    samples.append(create_sample_grayscale_sequence(str(sample_dir / "sample_sequence.npy"), num_frames=20))
    print()
    
    print("[3/3] Large video for performance test")
    samples.append(create_sample_large_video(str(sample_dir / "sample_large_video.npy"), num_frames=100))
    print()
    
    print("=" * 60)
    print("✓ All samples created successfully!")
    print("=" * 60)
    print()
    print("Next steps:")
    print("  1. Expand frames:")
    print("     python expand_multiframe.py sample/sample_video.npy")
    print()
    print("  2. Open in PixelScopeViewer:")
    print("     python main.py")
    print("     - Ctrl+O and select all frame files")
    print("     - Use 'n' and 'b' to navigate frames")
    print()


if __name__ == "__main__":
    main()
