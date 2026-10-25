"""ROI 一覧の CSV ファイルの保存・読み込み（Qt 非依存）。"""

from __future__ import annotations

import csv
import re
from pathlib import Path

COLUMNS = ("name", "x", "y", "width", "height", "enabled")
_NAME_PATTERN = re.compile(r"R(\d+)")
_INT_KEYS = ("x", "y", "width", "height")


def save_rois(path: str | Path, rois: list[dict]) -> None:
    """ROI 一覧を CSV ファイルに保存する。

    列は name（R{id}）, x, y, width, height, enabled（1 / 0）。

    Args:
        path: 保存先のパス。
        rois: id, x, y, width, height, enabled を持つ dict のリスト。
    """
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for r in rois:
            writer.writerow([f"R{int(r['id'])}", *(int(r[k]) for k in _INT_KEYS), int(bool(r.get("enabled", True)))])


def load_rois(path: str | Path) -> list[dict]:
    """CSV ファイルから ROI 一覧を読み込む。

    enabled 列は省略でき、1 / 0 と true / false を受け付ける。画像の範囲外にある ROI もそのまま返す。

    Returns:
        save_rois と同じ形式の dict のリスト。

    Raises:
        ValueError: 形式が不正な場合。
    """
    # Excel で保存した CSV の BOM を許容する
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        header = [h.strip() for h in reader.fieldnames or []]
        missing = [c for c in COLUMNS[:-1] if c not in header]
        if missing:
            raise ValueError(f"列 {', '.join(missing)} がありません（必要な列: {', '.join(COLUMNS)}）")
        reader.fieldnames = header
        rows = list(reader)

    rois = []
    ids = set()
    for line, row in enumerate(rows, start=2):
        if not any((v or "").strip() for v in row.values()):
            continue  # 空行
        m = _NAME_PATTERN.fullmatch((row["name"] or "").strip())
        if m is None:
            raise ValueError(f"{line} 行目: name は R0, R1, … の形式にしてください")
        roi_id = int(m.group(1))
        if roi_id in ids:
            raise ValueError(f"{line} 行目: name {row['name'].strip()} が重複しています")
        try:
            values = {k: int((row[k] or "").strip()) for k in _INT_KEYS}
        except ValueError as e:
            raise ValueError(f"{line} 行目: x, y, width, height は整数にしてください") from e
        if values["width"] <= 0 or values["height"] <= 0:
            raise ValueError(f"{line} 行目: width と height は正の値にしてください")
        if values["x"] < 0 or values["y"] < 0:
            raise ValueError(f"{line} 行目: x と y は 0 以上にしてください")
        enabled_text = (row.get("enabled") or "1").strip().lower()
        if enabled_text not in ("1", "0", "true", "false"):
            raise ValueError(f"{line} 行目: enabled は 1 / 0 にしてください")
        ids.add(roi_id)
        rois.append({"id": roi_id, **values, "enabled": enabled_text in ("1", "true")})
    return rois
