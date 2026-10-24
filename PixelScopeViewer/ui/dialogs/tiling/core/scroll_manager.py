"""複数画像比較の scroll 同期。"""

from PySide6.QtCore import QCoreApplication


class ScrollManager:
    """全 tile の scroll 位置を同期する。"""

    def __init__(self, tiles: list):
        self.tiles = tiles
        self._syncing_scroll = False

    def sync_scroll(self, source_index: int, direction: str, value: int, scale: float):
        """source の tile の scroll 位置を他の tile に同期する。

        画像や viewport のサイズが異なっても表示範囲が揃うよう、
        viewport 中心の相対位置 (value + pageStep/2) / (maximum + pageStep) を合わせる。

        Args:
            source_index: scroll した tile の index。
            direction: 'h'（水平）または 'v'（垂直）。
            value: source の scroll 値。
            scale: 現在の zoom 倍率。
        """
        if self._syncing_scroll:
            return

        src_sb = (
            self.tiles[source_index].scroll_area.horizontalScrollBar()
            if direction == "h"
            else self.tiles[source_index].scroll_area.verticalScrollBar()
        )
        if src_sb is None:
            return
        src_max = src_sb.maximum()
        src_page = src_sb.pageStep()
        denom = src_max + src_page
        if denom <= 0:
            return
        src_val = value
        # viewport 中心の相対位置 [0, 1]
        center_pos = src_val + (src_page / 2.0)
        ratio = max(0.0, min(1.0, center_pos / float(denom)))

        self._syncing_scroll = True
        try:
            for i, tile in enumerate(self.tiles):
                if i == source_index:
                    continue
                tgt_sb = (
                    tile.scroll_area.horizontalScrollBar() if direction == "h" else tile.scroll_area.verticalScrollBar()
                )
                if tgt_sb is None:
                    continue
                tgt_max = tgt_sb.maximum()
                tgt_page = tgt_sb.pageStep()
                tgt_denom = tgt_max + tgt_page
                if tgt_denom <= 0:
                    continue
                tgt_center = ratio * float(tgt_denom)
                tgt_val = int(round(tgt_center - (tgt_page / 2.0)))
                if tgt_val < tgt_sb.minimum():
                    tgt_val = tgt_sb.minimum()
                if tgt_val > tgt_sb.maximum():
                    tgt_val = tgt_sb.maximum()

                if tgt_sb.value() == tgt_val:
                    continue

                # 再帰は _syncing_scroll で防ぐ（blockSignals を使うと viewport が更新されない）
                tgt_sb.setValue(tgt_val)

                # 変更を即座に反映させる
                tile.scroll_area.update()
                tile.scroll_area.viewport().update()
                QCoreApplication.processEvents()

        finally:
            self._syncing_scroll = False

    def apply_scroll_position(self, new_scroll_x: float, new_scroll_y: float):
        """全 tile の scroll 位置を設定する。"""
        self._syncing_scroll = True
        try:
            for tile in self.tiles:
                tile_hsb = tile.scroll_area.horizontalScrollBar()
                tile_vsb = tile.scroll_area.verticalScrollBar()

                if tile_hsb:
                    clamped_x = max(tile_hsb.minimum(), min(new_scroll_x, tile_hsb.maximum()))
                    tile_hsb.setValue(int(clamped_x))
                if tile_vsb:
                    clamped_y = max(tile_vsb.minimum(), min(new_scroll_y, tile_vsb.maximum()))
                    tile_vsb.setValue(int(clamped_y))
        finally:
            self._syncing_scroll = False

    def scroll_by_key(self, active_tile_index: int, dx: int, dy: int):
        """矢印キーによる scroll を全 tile に適用する。

        Args:
            active_tile_index: active な tile の index。
            dx: 水平方向の移動量（正: 右）。
            dy: 垂直方向の移動量（正: 下）。

        Returns:
            scroll したか。
        """
        if not self.tiles or active_tile_index >= len(self.tiles):
            return False

        active_tile = self.tiles[active_tile_index]
        scroll_area = active_tile.scroll_area

        if dx != 0:
            hsb = scroll_area.horizontalScrollBar()
            if hsb:
                new_val = hsb.value() + dx
                new_val = max(hsb.minimum(), min(hsb.maximum(), new_val))
                hsb.setValue(new_val)
                self.sync_scroll(active_tile_index, "h", new_val, 1.0)

        if dy != 0:
            vsb = scroll_area.verticalScrollBar()
            if vsb:
                new_val = vsb.value() + dy
                new_val = max(vsb.minimum(), min(vsb.maximum(), new_val))
                vsb.setValue(new_val)
                self.sync_scroll(active_tile_index, "v", new_val, 1.0)

        return True
