import sys
from pathlib import Path

# Add parent directory to path to import pyside_image_viewer module
sys.path.insert(0, str(Path(__file__).parent.parent))

from pyside_image_viewer.core.image_io import get_image_metadata

# Test with sample image (adjust path relative to project root)
sample_path = Path(__file__).parent.parent / "sample" / "DSC04494.JPG"
metadata = get_image_metadata(str(sample_path))
print("Total tags:", len(metadata))
print("\nAll EXIF tags:")
for k, v in sorted(metadata.items()):
    print(f"{k}: {v}")
