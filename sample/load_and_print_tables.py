import json
import pandas as pd
from collections import OrderedDict


def flatten_dict(d, parent_key="", sep="_"):
    items = {}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(flatten_dict(v, new_key, sep=sep))
        else:
            items[new_key] = v
    return items


def load_and_print_tables(json_path):
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    dataset_name = data.get("dataset_name")
    print(f"Dataset Name: {dataset_name}")
    print()

    # Categories table
    categories_df = pd.DataFrame(data.get("categories", []))
    print("Categories Table:")
    print(categories_df.to_string(index=False))
    print()

    # Images table (flattened)
    images_rows = []
    for img in data.get("images", []):
        base = OrderedDict()
        base["id"] = img.get("id")
        base["file_name"] = img.get("file_name")

        # Flatten other keys (e.g., metrics)
        other = {k: v for k, v in img.items() if k not in ("id", "file_name", "annotations")}
        flat = flatten_dict(other)
        base.update(flat)

        # Summarize annotations
        anns = img.get("annotations") or []
        base["annotations_count"] = len(anns)
        images_rows.append(base)

    images_df = pd.DataFrame(images_rows)
    print("Images Table:")
    print(images_df.to_string(index=False))
    print()

    # Annotations table
    annotations_rows = []
    ann_id = 1
    for img in data.get("images", []):
        for a in img.get("annotations") or []:
            bbox = a.get("bbox", [None] * 4)
            annotations_rows.append(
                {
                    "annotation_id": ann_id,
                    "image_id": img.get("id"),
                    "category_id": a.get("category_id"),
                    "bbox_x": bbox[0],
                    "bbox_y": bbox[1],
                    "bbox_w": bbox[2],
                    "bbox_h": bbox[3],
                }
            )
            ann_id += 1

    annotations_df = pd.DataFrame(annotations_rows)
    print("Annotations Table:")
    print(annotations_df.to_string(index=False))


if __name__ == "__main__":
    load_and_print_tables("feature.json")
