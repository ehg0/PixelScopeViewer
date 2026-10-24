"""特徴量ファイル（JSON/CSV）の読み込みと管理。"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import polars as pl


def _flatten_dict(d: dict[str, Any], parent_key: str = "", sep: str = "_") -> dict[str, Any]:
    items: dict[str, Any] = {}
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.update(_flatten_dict(v, new_key, sep=sep))
        else:
            items[new_key] = v
    return items


class FeaturesManager:
    """fullfilepath を key として特徴量の行を管理する。

    同じ key の行は後から読み込んだもので置き換え、読み込み順を保持する。
    """

    # ユーザーが編集できない列
    NON_EDITABLE_COLUMNS = {"fullfilepath", "file_name"}

    def __init__(self) -> None:
        self._rows_by_key: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._dataset_name: str | None = None
        # JSON ファイルごとの categories
        self._categories_by_source: dict[str, list[dict[str, Any]]] = {}
        self._annotations_rows: list[dict[str, Any]] = []  # image_id, category_id, bbox(4 要素の list)
        # 保存 dialog の初期パスに使う
        self._last_loaded_path: str | None = None

    # ------------------------
    # 読み込み
    # ------------------------
    def load_feature_files(self, paths: Iterable[str]) -> int:
        """JSON/CSV の特徴量ファイルを読み込む。

        Returns:
            追加・置換した行数。
        """
        total = 0
        for p in paths or []:
            ext = Path(p).suffix.lower()
            if ext == ".json":
                total += self.load_json(p)
            elif ext == ".csv":
                total += self.load_csv(p)
        return total

    def load_json(self, json_path: str) -> int:
        """sample/feature.json 形式の JSON を読み込み、現在の表に統合する。

        Returns:
            追加・置換した行数。
        """
        path = Path(json_path)
        self._last_loaded_path = str(path.resolve())
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        if data.get("dataset_name"):
            self._dataset_name = data.get("dataset_name")

        json_key = str(path.resolve())
        cats = []
        for cat in data.get("categories", []) or []:
            if cat.get("id") is not None:
                cats.append(dict(cat))
        if cats:
            self._categories_by_source[json_key] = cats

        images_rows: list[dict[str, Any]] = []
        for img in data.get("images", []) or []:
            base: dict[str, Any] = OrderedDict()
            base["id"] = img.get("id")
            base["file_name"] = img.get("file_name")

            other = {k: v for k, v in img.items() if k not in ("id", "file_name", "annotations")}
            flat = _flatten_dict(other)
            base.update(flat)

            anns = img.get("annotations") or []
            base["annotations_count"] = len(anns)
            for a in anns:
                bbox = a.get("bbox") or [None, None, None, None]
                self._annotations_rows.append(
                    {
                        "image_id": img.get("id"),
                        "category_id": a.get("category_id"),
                        "bbox": [bbox[0], bbox[1], bbox[2], bbox[3]],
                    }
                )

            # JSON ファイルのディレクトリを基準に絶対パスを求める
            if base.get("file_name"):
                full = (path.parent / str(base["file_name"]).strip()).resolve()
                base["fullfilepath"] = str(full)
            images_rows.append(base)

        images_rows.sort(key=lambda x: x.get("id") if x.get("id") is not None else float("inf"))

        return self._merge_rows(images_rows)

    def load_csv(self, csv_path: str) -> int:
        """CSV を読み込み、現在の表に統合する。

        fullfilepath 列がなく file_name 列がある場合は、CSV のディレクトリを基準に fullfilepath を補う。

        Returns:
            追加・置換した行数。
        """
        path = Path(csv_path)
        self._last_loaded_path = str(path.resolve())
        try:
            df = pl.read_csv(str(path))
        except Exception:
            df = pl.DataFrame([])

        rows: list[dict[str, Any]] = df.to_dicts()

        for r in rows:
            if not r.get("fullfilepath") and r.get("file_name"):
                full = (path.parent / str(r["file_name"]).strip()).resolve()
                r["fullfilepath"] = str(full)
            elif not r.get("fullfilepath") and r.get("file_name") is None:
                # 解決できないのでそのまま残す
                pass

        return self._merge_rows(rows)

    # ------------------------
    # 内部処理
    # ------------------------
    def _merge_rows(self, rows: Iterable[dict[str, Any]]) -> int:
        """fullfilepath を key に行を統合する（後勝ち）。

        Returns:
            追加・置換した行数。
        """
        affected = 0
        for r in rows or []:
            key = r.get("fullfilepath")
            if not key:
                continue
            key = str(Path(key).resolve())

            # 既存の key は一度削除して末尾に移動する
            if key in self._rows_by_key:
                del self._rows_by_key[key]
            self._rows_by_key[key] = dict(r)
            self._rows_by_key[key]["fullfilepath"] = key
            affected += 1
        return affected

    # ------------------------
    # 参照・更新
    # ------------------------
    def get_rows(self) -> list[dict[str, Any]]:
        return list(self._rows_by_key.values())

    def get_columns(self) -> list[str]:
        """列名を id, file_name, fullfilepath, その他の順で返す。"""
        cols = OrderedDict()
        has_id = False
        has_file_name = False
        for r in self._rows_by_key.values():
            if "id" in r:
                has_id = True
            if "file_name" in r:
                has_file_name = True
            if has_id and has_file_name:
                break
        if has_id and has_file_name:
            cols["id"] = True
            cols["file_name"] = True
        cols["fullfilepath"] = True
        for r in self._rows_by_key.values():
            for k in r:
                cols.setdefault(k, True)
        return list(cols.keys())

    def to_polars(self) -> pl.DataFrame:
        rows = self.get_rows()
        if not rows:
            return pl.DataFrame([])
        return pl.DataFrame(rows)

    def get_last_loaded_directory(self) -> str | None:
        if self._last_loaded_path:
            return str(Path(self._last_loaded_path).parent)
        return None

    def get_last_loaded_path(self) -> str | None:
        return self._last_loaded_path

    def get_categories_rows(self) -> list[dict[str, Any]]:
        """全 JSON の categories を id で重複排除して返す（後勝ち）。"""
        merged: OrderedDict[int, dict[str, Any]] = OrderedDict()
        for cats in self._categories_by_source.values():
            for c in cats:
                cid = c.get("id")
                if cid is not None:
                    merged[cid] = dict(c)
        return list(merged.values())

    def get_categories_columns(self) -> list[str]:
        cols = OrderedDict()
        for r in self.get_categories_rows():
            for k in r:
                cols.setdefault(k, True)
        return list(cols.keys())

    def get_annotations_rows(self) -> list[dict[str, Any]]:
        return list(self._annotations_rows)

    def add_column(self, name: str, default_value: Any = None) -> None:
        """全行に列を追加する。"""
        name = name.strip()
        if not name:
            return
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

    # ------------------------
    # 書き出し
    # ------------------------
    def save_to_csv(self, save_path: str) -> None:
        df = self.to_polars()
        df.write_csv(save_path)

    def save_to_json(self, save_path: str) -> None:
        """sample/feature.json と同じ入れ子構造の JSON で保存する。"""
        images_rows = self.get_rows()

        images_list: list[dict[str, Any]] = []
        for r in images_rows:
            img_obj: dict[str, Any] = {}
            for k in ("id", "file_name", "width", "height"):
                if k in r:
                    img_obj[k] = r.get(k)

            # metrics_ で始まる列は metrics にまとめ、それ以外はそのまま出力する
            reserved = {"fullfilepath", "file_name"}
            metrics: dict[str, Any] = {}
            for k, v in r.items():
                if k in reserved or k in ("id", "width", "height"):
                    continue
                if k.startswith("metrics_"):
                    metrics[k.split("metrics_", 1)[1]] = v
                elif k != "annotations_count":
                    img_obj[k] = v

            if metrics:
                img_obj["metrics"] = metrics

            # image_id が一致する annotations を付与する
            anns: list[dict[str, Any]] = []
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

        categories_list = self.get_categories_rows()

        out = {
            "dataset_name": self._dataset_name or "dataset",
            "categories": categories_list,
            "images": images_list,
        }

        with open(save_path, "w", encoding="utf-8") as f:
            content = json.dumps(out, ensure_ascii=False, indent=2, separators=(",", ": "))
            # 小さな配列・object は 1 行にまとめる
            # bbox: [<num>, <num>, <num>, <num>]
            content = re.sub(
                r"\[\s+(-?\d+(?:\.\d+)?|null),\s+(-?\d+(?:\.\d+)?|null),\s+(-?\d+(?:\.\d+)?|null),\s+(-?\d+(?:\.\d+)?|null)\s+\]",
                r"[\1, \2, \3, \4]",
                content,
            )
            # category: {"id": X, "name": "Y"}
            content = re.sub(r'\{\s+"id":\s+(\d+),\s+"name":\s+"([^"]+)"\s+\}', r'{"id": \1, "name": "\2"}', content)
            # annotation: {"category_id": X, "bbox": [...]}
            content = re.sub(
                r'\{\s+"category_id":\s+(\d+),\s+"bbox":\s+(\[[^\]]+\])\s+\}',
                r'{"category_id": \1, "bbox": \2}',
                content,
            )
            f.write(content)
            f.write("\n")
