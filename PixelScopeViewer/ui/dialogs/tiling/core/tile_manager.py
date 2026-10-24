"""複数画像比較の tile の生成と並べ替え。"""

from PySide6.QtWidgets import QGridLayout

from PixelScopeViewer.ui.dialogs.tiling.core.utils import determine_dtype_group


class TileManager:
    """tile widget の生成・active 状態・並べ替えを管理する。"""

    def __init__(self, grid_layout: QGridLayout):
        self.grid_layout = grid_layout
        self.tiles: list = []
        self.tile_dtype_groups: list[str] = []
        self.displayed_image_data: list[dict] = []
        self.active_tile_index = 0

    def rebuild_tiles(
        self,
        all_images: list[dict],
        selected_indices: list[int],
        grid_size: tuple[int, int],
        parent_dialog,
        tile_widget_class,
        on_activated_func,
        on_roi_changed_func,
        on_mouse_coords_changed_func,
        on_scroll_func,
    ):
        """選択した画像の tile を作成して grid に配置する。

        Args:
            all_images: 全画像の dict のリスト。
            selected_indices: tile に表示する画像の index。
            grid_size: (行数, 列数)。
            parent_dialog: 親 dialog。
            tile_widget_class: tile の widget class。
            on_activated_func: tile が active になったときの callback。
            on_roi_changed_func: ROI の変更時の callback。
            on_mouse_coords_changed_func: マウス座標の変更時の callback。
            on_scroll_func: scroll 時の callback。
        """
        rows, cols = grid_size

        for i, img_idx in enumerate(selected_indices):
            if img_idx >= len(all_images):
                continue

            image_data = all_images[img_idx].copy()
            self.displayed_image_data.append(image_data)

            arr = image_data.get("base_array", image_data.get("array"))
            dtype_group = determine_dtype_group(arr)
            self.tile_dtype_groups.append(dtype_group)

            tile = tile_widget_class(image_data, parent_dialog, i)
            tile.activated.connect(lambda idx=i: on_activated_func(idx))
            tile.roi_changed.connect(on_roi_changed_func)
            tile.mouse_coords_changed.connect(on_mouse_coords_changed_func)

            self.tiles.append(tile)

            row = i // cols
            col = i % cols
            self.grid_layout.addWidget(tile, row, col)

            # 初回の表示は manager の初期化後に行う
            # signal の競合を避けるため、scroll の同期は sliderMoved（thumb の drag）のみで行う
            if tile.scroll_area.horizontalScrollBar():
                hsb = tile.scroll_area.horizontalScrollBar()
                hsb.sliderMoved.connect(lambda val, idx=i: on_scroll_func(idx, "h", val, "sliderMoved"))
            if tile.scroll_area.verticalScrollBar():
                vsb = tile.scroll_area.verticalScrollBar()
                vsb.sliderMoved.connect(lambda val, idx=i: on_scroll_func(idx, "v", val, "sliderMoved"))

    def set_active_tile(self, tile_index: int):
        if tile_index < 0 or tile_index >= len(self.tiles):
            return

        if 0 <= self.active_tile_index < len(self.tiles):
            self.tiles[self.active_tile_index].set_active(False)

        self.active_tile_index = tile_index
        self.tiles[tile_index].set_active(True)

    def get_active_tile_index(self) -> int:
        return self.active_tile_index

    def get_tiles(self) -> list:
        return self.tiles

    def get_tile_dtype_groups(self) -> list[str]:
        return self.tile_dtype_groups

    def get_displayed_image_data(self) -> list[dict]:
        return self.displayed_image_data
