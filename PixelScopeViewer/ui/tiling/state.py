"""複数画像比較の現在値。"""

from dataclasses import dataclass, field

from PySide6.QtCore import QRect

from PixelScopeViewer.core.constants import get_dtype_defaults
from PixelScopeViewer.ui.common import defaults


def _brightness_by_dtype() -> dict[str, dict[str, float]]:
    params = {}
    for dtype_key in ["uint8", "uint16", "float"]:
        d = get_dtype_defaults(dtype_key)
        params[dtype_key] = {"offset": d["initial_offset"], "upper_level": d["initial_upper_level"]}
    return params


@dataclass
class TilingState:
    """TilingDialog の現在値。各 manager が同じ instance を読み書きする。"""

    grid_size: tuple[int, int] = defaults.TILE_GRID_SIZE  # (rows, cols)
    # 比較する画像の index（表示順）
    selected_indices: list[int] = field(default_factory=list)
    active_tile_index: int = 0
    # 全 tile 共通の zoom と、fit zoom の切り替え前の倍率
    scale: float = 1.0
    is_fit_zoom: bool = False
    previous_zoom: float = 1.0
    # gain は全 tile 共通、offset・upper level は dtype group ごと
    brightness_gain: float = 1.0
    brightness_by_dtype: dict[str, dict[str, float]] = field(default_factory=_brightness_by_dtype)
    # 全 tile 共通の ROI（画像座標）
    common_roi: QRect | None = None
    # 解析 dialog で個別に設定した重ね描きの色（curve label "Tile n Ck" → hex）
    overlay_color_overrides: dict[str, str] = field(default_factory=dict)
