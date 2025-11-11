"""Generate a large features JSON file for testing PixelScopeViewer.

Usage:
    python sample/generate_large_features.py --out sample/large_features.json --images 1000 --metrics 500 --anns 3

This will create a JSON with the expected structure:
{
  "dataset_name": "dataset",
  "categories": [ ... ],
  "images": [ {"id": ..., "file_name": ..., "metrics": {...}, "annotations": [...]}, ... ]
}

Notes:
- Keep an eye on disk space when creating very large files.
- The script writes incrementally to avoid holding everything in memory for extremely large sizes.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import List, Dict, Any


def generate_image_obj(i: int, metrics_len: int, anns_per_image: int, categories_count: int) -> Dict[str, Any]:
    file_name = f"image_{i:06d}.png"
    # Some nested dict to test flattening
    metrics = {
        "histogram": [random.randint(0, 255) for _ in range(metrics_len)],
        "mean": random.random() * 255,
        "std": random.random() * 50,
    }
    # annotations
    anns = []
    for a in range(anns_per_image):
        cat = random.randint(0, categories_count - 1)
        # bboxes: [x, y, w, h]
        bbox = [
            round(random.random() * 1000, 2),
            round(random.random() * 1000, 2),
            round(random.random() * 200, 2),
            round(random.random() * 200, 2),
        ]
        anns.append({"category_id": cat, "bbox": bbox})

    img_obj: Dict[str, Any] = {
        "id": i,
        "file_name": file_name,
        "width": 1024,
        "height": 768,
        # include some other nested info to be flattened by FeaturesManager
        "camera": {"make": "TestCam", "model": "TC-1"},
        "metrics": metrics,
        "annotations": anns,
    }
    return img_obj


def generate_categories(n: int) -> List[Dict[str, Any]]:
    cats = []
    for i in range(n):
        cats.append({"id": i, "name": f"cat_{i}"})
    return cats


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="sample/large_features.json", help="Output JSON path")
    p.add_argument("--images", type=int, default=1000, help="Number of image rows to generate")
    p.add_argument("--metrics", type=int, default=256, help="Length of metrics histogram per image")
    p.add_argument("--anns", type=int, default=2, help="Annotations per image")
    p.add_argument("--cats", type=int, default=10, help="Number of categories")
    args = p.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Build header (dataset and categories)
    out = {
        "dataset_name": "large_dataset",
        "categories": generate_categories(args.cats),
        "images": [],
    }

    # For large size we stream images to file to avoid holding huge Python objects.
    # We'll write opening part, then append image objects separated by commas, then close array.

    with open(out_path, "w", encoding="utf-8") as f:
        # write head
        head = {"dataset_name": out["dataset_name"], "categories": out["categories"], "images": []}
        # Dump head without images
        f.write(json.dumps(head, ensure_ascii=False, indent=2, separators=(",", ": "))[:-3])
        f.write("\n")

        # Stream images
        for i in range(args.images):
            img = generate_image_obj(i, args.metrics, args.anns, args.cats)
            img_json = json.dumps(img, ensure_ascii=False, separators=(",", ": "))
            if i == 0:
                f.write("  " + img_json)
            else:
                f.write(",\n  " + img_json)
        # Close images array and root object
        f.write("\n  ]\n}\n")

    print(f"Wrote {args.images} images to {out_path} (metrics len={args.metrics}, anns per image={args.anns})")


if __name__ == "__main__":
    main()
