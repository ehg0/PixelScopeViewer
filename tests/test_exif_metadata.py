"""Test script for EXIF metadata extraction functionality.

This test script validates the image metadata extraction capabilities
using the core image_io module.
"""

import sys
from pathlib import Path

# Add parent directory to path to import pyside_image_viewer module
sys.path.insert(0, str(Path(__file__).parent.parent))

from pyside_image_viewer.core.image_io import get_image_metadata


def test_metadata_extraction():
    """Test metadata extraction with sample image."""
    # Test with sample image (adjust path relative to project root)
    sample_path = Path(__file__).parent.parent / "sample" / "DSC04494.JPG"

    if not sample_path.exists():
        print(f"Sample image not found at: {sample_path}")
        print("Please add a sample image file for testing.")
        return

    metadata = get_image_metadata(str(sample_path))
    print(f"Total metadata tags: {len(metadata)}")
    print("\nAll metadata tags:")
    for k, v in sorted(metadata.items()):
        print(f"{k}: {v}")


if __name__ == "__main__":
    test_metadata_extraction()
