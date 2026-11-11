"""メインビューアの現在値。"""

from dataclasses import dataclass, field

import numpy as np
from PySide6.QtCore import QRect

from PixelScopeViewer.core.brightness import BrightnessParams, determine_dtype_group
from PixelScopeViewer.core.constants import DTYPE_DEFAULTS
from PixelScopeViewer.core.tile_layout import Cell, TileLayout
from PixelScopeViewer.ui.common import defaults

# タイル比較モードで全タイル共通の brightness を保存する brightness_by_dtype の key
TILE_BRIGHTNESS_KEY = "tile"


def _brightness_by_dtype() -> dict[str, BrightnessParams]:
    return {key: BrightnessParams.for_dtype(key) for key in DTYPE_DEFAULTS}


def _tile_layout() -> TileLayout:
    return TileLayout(*defaults.TILE_MAX_GRID, *defaults.TILE_GRID_SIZE)


@dataclass
class RoiEntry:
    """ROI 一覧に登録した ROI。名前は id から決まる R{id} で固定する。"""

    id: int
    # 画像座標
    rect: QRect
    # 解析 dialog の「登録ROI」表示に含めるか
    enabled: bool = True

    @property
    def name(self) -> str:
        return f"R{self.id}"


@dataclass
class ViewerState:
    """ImageViewer の現在値。表示中の画像・zoom・ROI・brightness を持つ。"""

    current_index: int | None = None
    scale: float = 1.0
    # fit zoom の切り替え前の倍率と表示中心（画像座標）
    fit_zoom_scale: float | None = None
    original_zoom_scale: float = 1.0
    original_center_coords: tuple[float, float] | None = None
    # 画像座標の ROI（編集中 ROI）
    roi: QRect | None = None
    # ROI 一覧。画像を切り替えても保持する
    rois: list[RoiEntry] = field(default_factory=list)
    next_roi_id: int = 0
    # 編集中 ROI の変更を反映する ROI 一覧の id（一覧で選択中の行）
    linked_roi_id: int | None = None
    # 解析 dialog で個別に設定した ROI のグラフの色（"R0 C0" などから hex 文字列）。画像上の枠の色にも使う
    roi_color_overrides: dict[str, str] = field(default_factory=dict)
    brightness: BrightnessParams = field(default_factory=lambda: BrightnessParams.for_dtype("uint8"))
    # 画像を切り替えても dtype（float/uint8/uint16）ごとに直前の設定を保つ。タイル比較モードは "tile" に保つ
    brightness_by_dtype: dict[str, BrightnessParams] = field(default_factory=_brightness_by_dtype)
    # タイル比較モード
    tile_mode: bool = False
    # 一度でもタイル比較モードにしたか（初回だけ fit する）
    tile_initialized: bool = False
    tile_layout: TileLayout = field(default_factory=_tile_layout)
    # 最後にクリックしたタイルのマス
    active_cell: Cell = (0, 0)

    def brightness_key(self, arr: np.ndarray | None) -> str | None:
        """arr の brightness を保存する brightness_by_dtype の key を返す。

        タイル比較モードでは dtype によらず共通の key にする。1 枚表示で arr が None の場合は None。
        """
        if self.tile_mode:
            return TILE_BRIGHTNESS_KEY
        return determine_dtype_group(arr) if arr is not None else None
