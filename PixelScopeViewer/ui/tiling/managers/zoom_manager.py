"""複数画像比較の zoom 管理。"""

import numpy as np

from PixelScopeViewer.core.constants import MAX_ZOOM_SCALE, MIN_ZOOM_SCALE
from PixelScopeViewer.ui.tiling.state import TilingState


class ZoomManager:
    """全 tile 共通の zoom 倍率を管理する。"""

    def __init__(self, tiles: list, get_active_tile_index_func, state: TilingState):
        self.tiles = tiles
        self.get_active_tile_index = get_active_tile_index_func
        self.state = state

    def adjust_zoom(self, factor: float, tile_index: int | None = None, mouse_pos=None):
        """全 tile の zoom 倍率に factor を掛ける。

        Args:
            factor: 倍率（2.0 で拡大、0.5 で縮小）。
            tile_index: zoom の基準にする tile の index。None の場合は active な tile。
            mouse_pos: 基準にする viewport 上のマウス位置。None の場合は viewport の中心。

        Returns:
            基準点の表示位置を保つための (scroll x, scroll y)。tile_index が不正な場合は None。
        """
        if tile_index is None:
            tile_index = self.get_active_tile_index()

        if not (0 <= tile_index < len(self.tiles)):
            return

        source_tile = self.tiles[tile_index]
        scroll_area = source_tile.scroll_area
        viewport = scroll_area.viewport()

        # zoom の前後で表示位置を保つ基準点（wheel はマウス位置、キーは viewport の中心）
        if mouse_pos is not None:
            viewport_x = mouse_pos.x()
            viewport_y = mouse_pos.y()
        else:
            viewport_x = viewport.width() / 2.0
            viewport_y = viewport.height() / 2.0

        hsb = scroll_area.horizontalScrollBar()
        vsb = scroll_area.verticalScrollBar()
        scroll_x = hsb.value() if hsb else 0
        scroll_y = vsb.value() if vsb else 0

        # 基準点の画像座標
        image_x = (scroll_x + viewport_x) / self.state.scale
        image_y = (scroll_y + viewport_y) / self.state.scale

        # メインビューアと同じ範囲に制限する
        self.state.scale *= factor
        self.state.scale = max(MIN_ZOOM_SCALE, min(self.state.scale, MAX_ZOOM_SCALE))

        # 手動で zoom したら fit 状態を解除する
        self.state.is_fit_zoom = False

        for tile in self.tiles:
            tile.set_zoom(self.state.scale)

        # 基準点が同じ viewport 上の位置に来る scroll 位置
        new_scroll_x = image_x * self.state.scale - viewport_x
        new_scroll_y = image_y * self.state.scale - viewport_y

        # 同期のずれを避けるため、呼び出し側で全 tile に適用する
        return new_scroll_x, new_scroll_y

    def toggle_fit_zoom(self, sync_scroll_func):
        """window に合わせた倍率と直前の倍率を切り替える。

        Args:
            sync_scroll_func: zoom 後に scroll 位置を同期する関数。
        """
        if not self.tiles:
            return

        if self.state.is_fit_zoom:
            self.state.scale = self.state.previous_zoom
            self.state.is_fit_zoom = False
        else:
            self.state.previous_zoom = self.state.scale

            active_tile = (
                self.tiles[self.get_active_tile_index()]
                if self.get_active_tile_index() < len(self.tiles)
                else self.tiles[0]
            )
            scroll_area = active_tile.scroll_area
            viewport = scroll_area.viewport()

            image_label = active_tile.image_label
            if image_label.qimage:
                img_width = image_label.qimage.width()
                img_height = image_label.qimage.height()
                viewport_width = viewport.width()
                viewport_height = viewport.height()

                # 1.0 を上限に、画像全体が収まる倍率を最も近い 2 の累乗に丸める
                scale_w = viewport_width / img_width if img_width > 0 else 1.0
                scale_h = viewport_height / img_height if img_height > 0 else 1.0
                fit_scale = min(scale_w, scale_h, 1.0)
                fit_scale = max(MIN_ZOOM_SCALE, min(MAX_ZOOM_SCALE, fit_scale))
                power = round(np.log2(fit_scale))
                self.state.scale = 2.0**power
            else:
                self.state.scale = 1.0

            self.state.is_fit_zoom = True

        for tile in self.tiles:
            tile.set_zoom(self.state.scale)

        active_idx = self.get_active_tile_index()
        if 0 <= active_idx < len(self.tiles):
            src_area = self.tiles[active_idx].scroll_area
            hsb = src_area.horizontalScrollBar()
            vsb = src_area.verticalScrollBar()
            if hsb:
                sync_scroll_func(active_idx, "h", hsb.value())
            if vsb:
                sync_scroll_func(active_idx, "v", vsb.value())

    def get_scale(self) -> float:
        return self.state.scale
