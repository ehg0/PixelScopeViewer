"""Features loading and management using Polars.

This module provides a small manager to:
- Load feature files in JSON (flattened) and CSV formats using polars
- Maintain a merged, editable in-memory table keyed by ``fullfilepath``
- Resolve duplicates by letting the last loaded row win
- Export the current table to CSV or JSON

Notes:
- For JSON, we follow the sample in ``sample/load_and_print_tables_polars.py``
  to build an ``images_df``-equivalent table, then add ``fullfilepath`` by
  joining the JSON file directory and ``file_name``.
- For CSV, if ``fullfilepath`` does not exist but ``file_name`` does, we add
  ``fullfilepath`` in the same way (relative to the CSV file directory).
"""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Iterable, List, Dict, Any, Optional

import polars as pl
import json


def _flatten_dict(d: Dict[str, Any], parent_key: str = "", sep: str = "_") -> Dict[str, Any]:
    items: Dict[str, Any] = {}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(_flatten_dict(v, new_key, sep=sep))
        else:
            items[new_key] = v
    return items


class FeaturesManager:
    """Manage feature rows keyed by fullfilepath.

    Internally we keep an OrderedDict mapping ``fullfilepath`` (str) -> row (dict).
    This makes it easy to replace rows on collision ("last wins") and to present
    a stable iteration order (by load sequence).
    """

    # Columns that should not be edited by the user
    NON_EDITABLE_COLUMNS = {"fullfilepath", "file_name"}

    def __init__(self) -> None:
        self._rows_by_key: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        # Optional rich data from JSON loads
        self._dataset_name: Optional[str] = None
        # Categories keyed by (source_json_path, category_id) to preserve per-file categories
        self._categories_by_source: "Dict[str, List[Dict[str, Any]]]" = {}
        self._annotations_rows: List[Dict[str, Any]] = []  # image_id, category_id, bbox(list of 4)
        # Track last loaded path for save dialog
        self._last_loaded_path: Optional[str] = None

    # ------------------------
    # Loaders
    # ------------------------
    def load_feature_files(self, paths: Iterable[str]) -> int:
        """Load multiple feature files (json or csv). Returns number of rows added/replaced."""
        total = 0
        for p in paths or []:
            ext = Path(p).suffix.lower()
            if ext == ".json":
                total += self.load_json(p)
            elif ext == ".csv":
                total += self.load_csv(p)
        return total

    def load_json(self, json_path: str) -> int:
        """Load a JSON feature file and merge into the current table.

        The JSON schema is expected to follow the sample in ``sample/feature.json``.
        Returns the number of rows inserted/replaced.
        """
        path = Path(json_path)
        self._last_loaded_path = str(path.resolve())  # Remember last loaded path
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # dataset_name
        if data.get("dataset_name"):
            self._dataset_name = data.get("dataset_name")

        # categories: store per source JSON path (fullfilepath-based merge)
        json_key = str(path.resolve())
        cats = []
        for cat in data.get("categories", []) or []:
            if cat.get("id") is not None:
                cats.append(dict(cat))
        if cats:
            self._categories_by_source[json_key] = cats

        images_rows: List[Dict[str, Any]] = []
        for img in data.get("images", []) or []:
            base: Dict[str, Any] = OrderedDict()
            base["id"] = img.get("id")
            base["file_name"] = img.get("file_name")

            other = {k: v for k, v in img.items() if k not in ("id", "file_name", "annotations")}
            flat = _flatten_dict(other)
            base.update(flat)

            anns = img.get("annotations") or []
            base["annotations_count"] = len(anns)
            # store annotations (flatten bbox fields but keep list for JSON save)
            for a in anns:
                bbox = a.get("bbox") or [None, None, None, None]
                self._annotations_rows.append(
                    {
                        "image_id": img.get("id"),
                        "category_id": a.get("category_id"),
                        "bbox": [bbox[0], bbox[1], bbox[2], bbox[3]],
                    }
                )

            # Compute absolute fullfilepath relative to the JSON file directory
            if base.get("file_name"):
                full = (path.parent / str(base["file_name"]).strip()).resolve()
                base["fullfilepath"] = str(full)
            images_rows.append(base)

        # Sort images_rows by id in ascending order before merging
        images_rows.sort(key=lambda x: x.get("id") if x.get("id") is not None else float("inf"))

        return self._merge_rows(images_rows)

    def load_csv(self, csv_path: str) -> int:
        """Load a CSV feature file and merge into the current table.

        If ``fullfilepath`` is missing but ``file_name`` exists, an absolute
        ``fullfilepath`` will be derived relative to the CSV file directory.
        Returns the number of rows inserted/replaced.
        """
        path = Path(csv_path)
        self._last_loaded_path = str(path.resolve())  # Remember last loaded path
        try:
            df = pl.read_csv(str(path))
        except Exception:
            # Fallback to empty
            df = pl.DataFrame([])

        rows: List[Dict[str, Any]] = df.to_dicts()

        # Ensure fullfilepath
        for r in rows:
            if not r.get("fullfilepath") and r.get("file_name"):
                full = (path.parent / str(r["file_name"]).strip()).resolve()
                r["fullfilepath"] = str(full)
            elif not r.get("fullfilepath") and r.get("file_name") is None:
                # As a last resort, keep as-is (may not be resolvable)
                pass

        return self._merge_rows(rows)

    # ------------------------
    # Core ops
    # ------------------------
    def _merge_rows(self, rows: Iterable[Dict[str, Any]]) -> int:
        """Merge given rows into current table. Last wins by 'fullfilepath'.

        Returns number of affected rows (inserted+replaced).
        """
        affected = 0
        for r in rows or []:
            key = r.get("fullfilepath")
            if not key:
                # Skip rows without identifiable key
                continue
            key = str(Path(key).resolve())

            # If key already exists, delete first to move it to the end (last wins + preserve order)
            if key in self._rows_by_key:
                del self._rows_by_key[key]
            self._rows_by_key[key] = dict(r)
            # Ensure normalized key stored
            self._rows_by_key[key]["fullfilepath"] = key
            affected += 1
        return affected

    # ------------------------
    # Accessors / Mutators
    # ------------------------
    def get_rows(self) -> List[Dict[str, Any]]:
        return list(self._rows_by_key.values())

    def get_columns(self) -> List[str]:
        cols = OrderedDict()
        # First check if id and file_name exist in any row
        has_id = False
        has_file_name = False
        for r in self._rows_by_key.values():
            if "id" in r:
                has_id = True
            if "file_name" in r:
                has_file_name = True
            if has_id and has_file_name:
                break
        # If both exist, put them first (id, file_name)
        if has_id and has_file_name:
            cols["id"] = True
            cols["file_name"] = True
        # Then fullfilepath
        cols["fullfilepath"] = True
        # Then all others
        for r in self._rows_by_key.values():
            for k in r.keys():
                cols.setdefault(k, True)
        return list(cols.keys())

    def to_polars(self) -> pl.DataFrame:
        rows = self.get_rows()
        if not rows:
            return pl.DataFrame([])
        return pl.DataFrame(rows)

    def get_last_loaded_directory(self) -> Optional[str]:
        """Return the directory of the last loaded feature file, or None."""
        if self._last_loaded_path:
            return str(Path(self._last_loaded_path).parent)
        return None

    def get_last_loaded_path(self) -> Optional[str]:
        """Return the full path of the last loaded feature file, or None."""
        return self._last_loaded_path

    def get_categories_rows(self) -> List[Dict[str, Any]]:
        # Flatten all categories from all sources, de-duplicate by id (last wins)
        merged: "OrderedDict[int, Dict[str, Any]]" = OrderedDict()
        for cats in self._categories_by_source.values():
            for c in cats:
                cid = c.get("id")
                if cid is not None:
                    merged[cid] = dict(c)
        return list(merged.values())

    def get_categories_columns(self) -> List[str]:
        cols = OrderedDict()
        for r in self.get_categories_rows():
            for k in r.keys():
                cols.setdefault(k, True)
        return list(cols.keys())

    def get_annotations_rows(self) -> List[Dict[str, Any]]:
        return list(self._annotations_rows)

    def get_annotations_columns(self) -> List[str]:
        cols = OrderedDict()
        # Standardize columns
        preferred = ["image_id", "category_id", "bbox_x", "bbox_y", "bbox_w", "bbox_h"]
        for p in preferred:
            cols[p] = True
        # ensure bbox split
        for r in self._annotations_rows:
            pass
        return list(cols.keys())

    def add_column(self, name: str, default_value: Any = None) -> None:
        name = name.strip()
        if not name:
            return
        # Add to all rows if missing
        for r in self._rows_by_key.values():
            if name not in r:
                r[name] = default_value

    def set_value(self, row_index: int, column: str, value: Any) -> None:
        if column in self.NON_EDITABLE_COLUMNS:
            return
        rows = self.get_rows()
        if 0 <= row_index < len(rows):
            key = rows[row_index].get("fullfilepath")
            if key and key in self._rows_by_key:
                self._rows_by_key[key][column] = value

    def get_value(self, row_index: int, column: str) -> Any:
        rows = self.get_rows()
        if 0 <= row_index < len(rows):
            return rows[row_index].get(column)
        return None

    def row_count(self) -> int:
        return len(self._rows_by_key)

    def column_is_editable(self, name: str) -> bool:
        return name not in self.NON_EDITABLE_COLUMNS

    def find_row_index_by_path(self, fullpath: str) -> Optional[int]:
        full = str(Path(fullpath).resolve())
        for i, r in enumerate(self.get_rows()):
            if str(Path(r.get("fullfilepath", "")).resolve()) == full:
                return i
        return None

    # ------------------------
    # Export helpers
    # ------------------------
    def save_to_csv(self, save_path: str) -> None:
        df = self.to_polars()
        df.write_csv(save_path)

    def save_to_json(self, save_path: str) -> None:
        """Save in the nested JSON structure like sample/feature.json."""
        images_rows = self.get_rows()

        # Build images with nested metrics and annotations
        images_list: List[Dict[str, Any]] = []
        for r in images_rows:
            img_obj: Dict[str, Any] = {}
            # Base fields
            for k in ("id", "file_name", "width", "height"):
                if k in r:
                    img_obj[k] = r.get(k)

            # Other keys (except reserved/edit control columns)
            reserved = {"fullfilepath", "file_name"}
            metrics: Dict[str, Any] = {}
            for k, v in r.items():
                if k in reserved or k in ("id", "width", "height"):
                    continue
                if k.startswith("metrics_"):
                    metrics[k.split("metrics_", 1)[1]] = v
                elif k != "annotations_count":
                    img_obj[k] = v

            if metrics:
                img_obj["metrics"] = metrics

            # Attach annotations by image_id
            anns: List[Dict[str, Any]] = []
            img_id = r.get("id")
            if img_id is not None:
                for a in self._annotations_rows:
                    if a.get("image_id") == img_id:
                        bbox = a.get("bbox") or [None, None, None, None]
                        anns.append(
                            {
                                "category_id": a.get("category_id"),
                                "bbox": [bbox[0], bbox[1], bbox[2], bbox[3]],
                            }
                        )
            img_obj["annotations"] = anns
            images_list.append(img_obj)

        # Categories list (if available)
        categories_list = self.get_categories_rows()

        out = {
            "dataset_name": self._dataset_name or "dataset",
            "categories": categories_list,
            "images": images_list,
        }

        # Write with compact arrays/objects (no newline after commas inside arrays)
        with open(save_path, "w", encoding="utf-8") as f:
            content = json.dumps(out, ensure_ascii=False, indent=2, separators=(",", ": "))
            # Post-process: remove newlines inside small arrays like bbox and category dicts
            # Pattern: keep arrays on single line if they're simple (numbers/nulls only)
            import re

            # Compact bbox arrays: [<num>, <num>, <num>, <num>]
            content = re.sub(
                r"\[\s+(-?\d+(?:\.\d+)?|null),\s+(-?\d+(?:\.\d+)?|null),\s+(-?\d+(?:\.\d+)?|null),\s+(-?\d+(?:\.\d+)?|null)\s+\]",
                r"[\1, \2, \3, \4]",
                content,
            )
            # Compact small objects like {"id": X, "name": "Y"} on single line
            content = re.sub(r'\{\s+"id":\s+(\d+),\s+"name":\s+"([^"]+)"\s+\}', r'{"id": \1, "name": "\2"}', content)
            # Compact category_id/bbox annotation objects
            content = re.sub(
                r'\{\s+"category_id":\s+(\d+),\s+"bbox":\s+(\[[^\]]+\])\s+\}',
                r'{"category_id": \1, "bbox": \2}',
                content,
            )
            f.write(content)
            f.write("\n")  # Add trailing newline
