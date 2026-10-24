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
import rawpy

# Import the registry to register our loader
from PixelScopeViewer.core.image_io import ImageLoaderRegistry


def dng_loader(path: str) -> np.ndarray | None:
    ext = Path(path).suffix.lower()
    if ext not in [".dng"]:
        return None

    try:
        raw = rawpy.imread(path)
        img_raw = raw.raw_image
        img_r = img_raw[0::2, 0::2]
        img_gr = img_raw[0::2, 1::2]
        img_gb = img_raw[1::2, 0::2]
        img_b = img_raw[1::2, 1::2]

        all_members = dir(raw)
        # print("すべてのメンバー:")
        # for member in all_members:
        #     print(member)

        # インスタンス変数のみを取得する (__ から始まる特殊属性を除く)
        instance_variables = [
            attr for attr in dir(raw) if not attr.startswith("__") and not callable(getattr(raw, attr))
        ]
        print("\nインスタンス変数のみ:")
        for var in instance_variables:
            try:
                value = getattr(raw, var)
                # 値の一部または型を表示 (データが大きい場合は注意)
                print(f"{var}: {value} {type(value)}")
            except Exception as e:
                print(f"{var}: 取得エラー - {e}")
        return {"SRC": img_raw, "R": img_r, "GR": img_gr, "GB": img_gb, "B": img_b}

    except Exception:
        # If loading fails, return None to try other loaders
        return None


# Register the loaders when this module is imported
# Higher priority values are tried first
registry = ImageLoaderRegistry.get_instance()

# Register specific format loaders with high priority
registry.register(dng_loader, extensions=[".dng"], priority=0)


# Register wildcard fallback with low priority
# Uncomment the line below if you want to enable wildcard loading:
# registry.register(wildcard_fallback_loader, extensions=['*'], priority=-100)
