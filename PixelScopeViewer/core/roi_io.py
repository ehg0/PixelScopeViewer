"""ROI 一覧の JSON ファイルの保存・読み込み（Qt 非依存）。"""

from __future__ import annotations

import json
from pathlib import Path

ROI_FILE_VERSION = 1
_RECT_KEYS = ("id", "x", "y", "width", "height")


def save_rois(path: str | Path, rois: list[dict], color_overrides: dict[str, str]) -> None:
    """ROI 一覧と色の個別設定を JSON ファイルに保存する。

    Args:
        path: 保存先のパス。
        rois: id, x, y, width, height, enabled を持つ dict のリスト。
        color_overrides: curve label（"R1 C0" など）から hex 文字列への dict。
    """
    data = {
        "version": ROI_FILE_VERSION,
        "rois": [{**{k: int(r[k]) for k in _RECT_KEYS}, "enabled": bool(r.get("enabled", True))} for r in rois],
        "color_overrides": dict(color_overrides),
    }
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_rois(path: str | Path) -> tuple[list[dict], dict[str, str]]:
    """JSON ファイルから ROI 一覧と色の個別設定を読み込む。

    画像の範囲外にある ROI もそのまま返す。

    Returns:
        (save_rois と同じ形式の ROI のリスト, 色の個別設定)。

    Raises:
        ValueError: 形式が不正な場合。
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON として読み込めません: {e}") from e
    if not isinstance(data, dict) or data.get("version") != ROI_FILE_VERSION:
        raise ValueError(f"ROI 一覧のファイルではないか、未対応の version です（対応: {ROI_FILE_VERSION}）")
    if not isinstance(data.get("rois"), list):
        raise ValueError("'rois' のリストがありません")

    rois = []
    ids = set()
    for i, r in enumerate(data["rois"]):
        if not isinstance(r, dict) or any(k not in r for k in _RECT_KEYS):
            raise ValueError(f"rois[{i}] に {', '.join(_RECT_KEYS)} のいずれかがありません")
        # bool は int の subclass のため除外する
        if any(not isinstance(r[k], int) or isinstance(r[k], bool) for k in _RECT_KEYS):
            raise ValueError(f"rois[{i}] の {', '.join(_RECT_KEYS)} は整数にしてください")
        if r["width"] <= 0 or r["height"] <= 0:
            raise ValueError(f"rois[{i}] の width と height は正の値にしてください")
        if r["x"] < 0 or r["y"] < 0:
            raise ValueError(f"rois[{i}] の x と y は 0 以上にしてください")
        if r["id"] <= 0 or r["id"] in ids:
            raise ValueError(f"rois[{i}] の id が正でないか、重複しています")
        enabled = r.get("enabled", True)
        if not isinstance(enabled, bool):
            raise ValueError(f"rois[{i}] の enabled は true / false にしてください")
        ids.add(r["id"])
        rois.append({**{k: r[k] for k in _RECT_KEYS}, "enabled": enabled})

    overrides = data.get("color_overrides", {})
    if not isinstance(overrides, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in overrides.items()
    ):
        raise ValueError("'color_overrides' は文字列から文字列への dict にしてください")
    return rois, overrides
