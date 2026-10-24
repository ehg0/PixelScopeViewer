"""メインビューアの現在値。"""

from dataclasses import dataclass, field

from PySide6.QtCore import QRect

from PixelScopeViewer.core.brightness import BrightnessParams
from PixelScopeViewer.core.constants import DTYPE_DEFAULTS


def _brightness_by_dtype() -> dict[str, BrightnessParams]:
    return {key: BrightnessParams.for_dtype(key) for key in DTYPE_DEFAULTS}


@dataclass
class ViewerState:
    """ImageViewer の現在値。表示中の画像・zoom・ROI・brightness を持つ。"""

    current_index: int | None = None
    scale: float = 1.0
    # fit zoom の切り替え前の倍率と表示中心（画像座標）
    fit_zoom_scale: float | None = None
    original_zoom_scale: float = 1.0
    original_center_coords: tuple[float, float] | None = None
    # 画像座標の ROI
    roi: QRect | None = None
    brightness: BrightnessParams = field(default_factory=lambda: BrightnessParams.for_dtype("uint8"))
    # 画像を切り替えても dtype（float/uint8/uint16）ごとに直前の設定を保つ
    brightness_by_dtype: dict[str, BrightnessParams] = field(default_factory=_brightness_by_dtype)
