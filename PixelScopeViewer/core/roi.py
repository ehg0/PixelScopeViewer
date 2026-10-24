"""ROI の当たり判定・作成・移動・リサイズの計算（Qt 非依存）。矩形はすべて (x, y, w, h)。"""

from __future__ import annotations

Rect = tuple[int, int, int, int]

# 辺からこの距離（表示 pixel）以内ならリサイズの対象にする
EDGE_GRAB_DISTANCE = 8


def hit_test_edge(px: int, py: int, rect: Rect, *, inclusive: bool, grab_dist: int = EDGE_GRAB_DISTANCE) -> str | None:
    """(px, py) の近くにある ROI の辺・角を返す。角を優先する。

    Args:
        px: 表示座標の x。
        py: 表示座標の y。
        rect: 表示座標の ROI。
        inclusive: 右端・下端を x + w - 1（QRect と同じ）とするか。False の場合は x + w。
        grab_dist: 辺からの判定距離。小さな ROI では、移動用の内側の領域が残るよう縮める。

    Returns:
        'tl', 'tr', 'bl', 'br', 'left', 'right', 'top', 'bottom' のいずれか。該当しない場合は None。
    """
    x, y, w, h = rect
    right = x + w - 1 if inclusive else x + w
    bottom = y + h - 1 if inclusive else y + h

    min_dimension = min(w, h)
    if min_dimension < grab_dist * 2:
        grab_dist = max(1, min_dimension // 3)

    near_left = abs(px - x) <= grab_dist
    near_right = abs(px - right) <= grab_dist
    near_top = abs(py - y) <= grab_dist
    near_bottom = abs(py - bottom) <= grab_dist
    inside_x = x <= px <= right
    inside_y = y <= py <= bottom

    for edge, hit in (
        ("tl", near_left and near_top),
        ("tr", near_right and near_top),
        ("bl", near_left and near_bottom),
        ("br", near_right and near_bottom),
        ("left", near_left and inside_y),
        ("right", near_right and inside_y),
        ("top", near_top and inside_x),
        ("bottom", near_bottom and inside_x),
    ):
        if hit:
            return edge
    return None


def rect_from_points(p0: tuple[int, int], p1: tuple[int, int]) -> Rect:
    """2 つの pixel を両端に含む矩形を返す。同じ pixel の場合は 1x1。"""
    x0, x1 = sorted((p0[0], p1[0]))
    y0, y1 = sorted((p0[1], p1[1]))
    return (x0, y0, x1 - x0 + 1, y1 - y0 + 1)


def move_rect(orig: Rect, dx: int, dy: int, img_w: int, img_h: int) -> Rect:
    """ROI を (dx, dy) だけ移動する。画像の範囲からはみ出さないよう止める。"""
    x, y, w, h = orig
    return (max(0, min(x + dx, img_w - w)), max(0, min(y + dy, img_h - h)), w, h)


def resize_rect(orig: Rect, edge: str, px: int, py: int, img_w: int, img_h: int) -> Rect:
    """ROI の辺・角 edge を画像座標 (px, py) まで動かした矩形を返す。

    反対側の辺は固定し、画像の範囲内で幅・高さは 1 以上に保つ。
    """
    x, y, w, h = orig
    new_x, new_y, new_w, new_h = orig

    # 水平方向（左右の辺と角）
    if edge in ("left", "tl", "bl"):
        new_x = max(0, min(px, x + w - 1))
        new_w = x + w - new_x
    elif edge in ("right", "tr", "br"):
        new_w = max(x, min(px, img_w - 1)) - x + 1

    # 垂直方向（上下の辺と角）
    if edge in ("top", "tl", "tr"):
        new_y = max(0, min(py, y + h - 1))
        new_h = y + h - new_y
    elif edge in ("bottom", "bl", "br"):
        new_h = max(y, min(py, img_h - 1)) - y + 1

    return (new_x, new_y, max(1, new_w), max(1, new_h))
