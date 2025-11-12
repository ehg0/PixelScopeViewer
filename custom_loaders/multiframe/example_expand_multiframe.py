"""Example: Using multiframe expansion in your own scripts.

This demonstrates how to programmatically expand 4D arrays
for use with PixelScopeViewer.
"""

import numpy as np
from expand_multiframe import expand_multiframe


# Example 1: Generate test data and expand
def create_test_multiframe():
    """Create a test 4D array and expand it."""
    # Create test data: 100 frames of 256x256 RGB images
    H, W, C, N = 256, 256, 3, 100
    
    print("Creating test data...")
    data = np.random.randint(0, 256, size=(H, W, C, N), dtype=np.uint8)
    
    # Add frame number as pattern (for easy identification)
    for i in range(N):
        # Add brightness gradient based on frame number
        brightness = int(255 * i / N)
        data[:, :, 0, i] = np.clip(data[:, :, 0, i] + brightness, 0, 255)
    
    # Save the multiframe data
    np.save('test_multiframe.npy', data)
    print(f"Saved test_multiframe.npy: shape={data.shape}")
    
    # Expand into individual frames
    expand_multiframe('test_multiframe.npy', 'test_frames')


# Example 2: Load existing multiframe and expand
def expand_existing_file(input_file: str):
    """Expand an existing multiframe file."""
    try:
        expand_multiframe(input_file)
        print("\n✓ Expansion complete!")
    except Exception as e:
        print(f"✗ Error: {e}")


# Example 3: Expand with custom settings
def expand_with_custom_settings():
    """Expand with custom output directory and prefix."""
    # Assume you have a file called 'video.npy'
    input_file = 'video.npy'
    output_dir = 'output/video_frames'
    
    # Check if file exists
    from pathlib import Path
    if not Path(input_file).exists():
        print(f"File not found: {input_file}")
        print("Creating test data instead...")
        create_test_multiframe()
        return
    
    # Expand with custom settings
    try:
        num_frames = expand_multiframe(
            input_path=input_file,
            output_dir=output_dir,
            prefix='video_frame'
        )
        print(f"\n✓ Created {num_frames} frames in {output_dir}")
    except Exception as e:
        print(f"✗ Error: {e}")


if __name__ == "__main__":
    # Run the example
    print("=" * 60)
    print("Multiframe Expansion Example")
    print("=" * 60)
    print()
    
    # Uncomment the example you want to run:
    
    # Example 1: Create test data
    create_test_multiframe()
    
    # Example 2: Expand existing file
    # expand_existing_file('your_file.npy')
    
    # Example 3: Custom settings
    # expand_with_custom_settings()
