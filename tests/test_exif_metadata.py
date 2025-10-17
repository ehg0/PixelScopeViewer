import sys

sys.path.insert(0, ".")
from pyside_image_viewer.core.image_io import get_image_metadata

metadata = get_image_metadata("sample/DSC04494.JPG")
print("Total tags:", len(metadata))
print("\nAll EXIF tags:")
for k, v in sorted(metadata.items()):
    print(f"{k}: {v}")
