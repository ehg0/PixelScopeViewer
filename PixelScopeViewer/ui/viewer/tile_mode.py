"""ImageViewer のタイル比較モード（切り替え・タイルの表示・scroll の同期・active タイル）。"""

from dataclasses import replace
from pathlib import Path

from PixelScopeViewer.core.brightness import BrightnessParams, determine_dtype_group
from PixelScopeViewer.core.tile_layout import Cell, TileLayout
from PixelScopeViewer.ui.viewer.widgets import ImagePane

TILE_BRIGHTNESS_KEY = "tile"


class TileModeManager:
    """メイン画面をグリッドに分割し、各マスの画像を同じ zoom・表示位置・ROI で表示する。

    pane はマスごとに 1 度だけ作り、(0, 0) のマスは 1 枚表示の pane と共有する。
    active タイルの画像の index を viewer.state.current_index に入れ、1 枚分の情報を出す機能はその画像を対象にする。
    """

    def __init__(self, viewer):
        self.viewer = viewer
        self._panes: dict[Cell, ImagePane] = {(0, 0): viewer.panes[0]}
        self._syncing = False

    @property
    def layout(self) -> TileLayout:
        return self.viewer.state.tile_layout

    @property
    def active(self) -> bool:
        return self.viewer.state.tile_mode

    def pane(self, cell: Cell) -> ImagePane:
        if cell not in self._panes:
            self._panes[cell] = ImagePane(self.viewer)
        return self._panes[cell]

    def cell_of(self, pane: ImagePane) -> Cell | None:
        return next((cell for cell, p in self._panes.items() if p is pane), None)

    def cell_at(self, widget, pos) -> Cell | None:
        """widget 座標 pos にある表示中のタイルのマスを返す。タイルの外の場合は None。"""
        for pane in self.viewer.panes:
            if pane.rect().contains(pane.mapFrom(widget, pos)):
                return self.cell_of(pane)
        return None

    # --- 切り替え ---
    def enter(self):
        """タイル比較モードにする。初めての場合は fit し、brightness を最初のタイルの画像の dtype の初期値にする。"""
        v = self.viewer
        st = v.state
        if st.tile_mode:
            self.apply_layout()
            v.brightness_manager.sync_tile_mode()
            v.show_current_image()
            return
        center = v.zoom_manager.calculate_viewport_center_in_image_coords() if v.has_image() else None
        first = not st.tile_initialized
        st.tile_mode = True
        st.tile_initialized = True
        if TILE_BRIGHTNESS_KEY not in st.brightness_by_dtype:
            first_img = self._first_visible_image()
            group = determine_dtype_group(first_img["array"]) if first_img is not None else "uint8"
            st.brightness_by_dtype[TILE_BRIGHTNESS_KEY] = BrightnessParams.for_dtype(group)
        st.brightness = replace(st.brightness_by_dtype[TILE_BRIGHTNESS_KEY])
        self.apply_layout()
        v.brightness_manager.sync_tile_mode()
        v.show_current_image()
        v.status_updater.update_brightness_status()
        if first or center is None:
            v.zoom_manager.fit_to_window()
        else:
            v.zoom_manager.set_zoom_at_coords(st.scale, center)

    def exit(self):
        """1 枚表示に戻す。active タイルの画像を表示する。"""
        v = self.viewer
        st = v.state
        if not st.tile_mode:
            return
        center = v.zoom_manager.calculate_viewport_center_in_image_coords() if v.has_image() else None
        st.tile_mode = False
        grid = v.pane_grid
        for pane in list(self._panes.values()):
            grid.removeWidget(pane)
            pane.hide()
        single = self._panes[(0, 0)]
        single.set_tile_mode(False)
        single.image_label.set_canvas_size(None)
        grid.addWidget(single, 0, 0)
        self._set_stretch(1, 1)
        single.show()
        v.panes = [single]
        v.active_pane = single
        if st.current_index is None and v.images:
            st.current_index = 0
        v.brightness_manager.sync_tile_mode()
        v.show_current_image()
        if center is not None and v.has_image():
            v.zoom_manager.set_zoom_at_coords(st.scale, center)

    def registered_dtype_groups(self) -> list[str]:
        """表示中のマスに登録されている画像の dtype の group を返す。先頭は最初のタイルの画像の dtype。"""
        v = self.viewer
        first = self._first_visible_image()
        groups = [determine_dtype_group(first["array"])] if first is not None else []
        for cell in self.layout.visible_cells():
            for image_id in self.layout.stack(cell):
                idx = v.image_list.index_of(image_id)
                if idx is not None and (g := determine_dtype_group(v.images[idx]["array"])) not in groups:
                    groups.append(g)
        return groups

    def _first_visible_image(self) -> dict | None:
        for image_id in self.layout.visible_image_ids():
            idx = self.viewer.image_list.index_of(image_id)
            if idx is not None:
                return self.viewer.images[idx]
        return None

    # --- グリッド ---
    def apply_layout(self):
        """表示するマスの pane をグリッドに並べ、active タイルを決める。"""
        v = self.viewer
        layout = self.layout
        grid = v.pane_grid
        for pane in list(self._panes.values()):
            grid.removeWidget(pane)
            pane.hide()
        cells = layout.visible_cells()
        for cell in cells:
            pane = self.pane(cell)
            pane.set_tile_mode(True)
            grid.addWidget(pane, *cell)
            pane.show()
        self._set_stretch(layout.rows, layout.cols)
        v.panes = [self.pane(cell) for cell in cells]
        if not layout.is_visible(v.state.active_cell):
            v.state.active_cell = (0, 0)
        self._set_active_pane(self.pane(v.state.active_cell))

    def _set_stretch(self, rows: int, cols: int):
        grid = self.viewer.pane_grid
        for r in range(self.layout.max_rows):
            grid.setRowStretch(r, 1 if r < rows else 0)
        for c in range(self.layout.max_cols):
            grid.setColumnStretch(c, 1 if c < cols else 0)

    def _set_active_pane(self, pane: ImagePane):
        self.viewer.active_pane = pane
        for p in self.viewer.panes:
            p.set_active(p is pane)

    # --- active タイル ---
    def set_active_cell(self, cell: Cell) -> bool:
        """active タイルを変え、active な画像が変わったことを viewer に通知する。

        Returns:
            active タイルが変わったか。
        """
        v = self.viewer
        if not self.active or not self.layout.is_visible(cell):
            return False
        pane = self.pane(cell)
        if cell == v.state.active_cell and pane is v.active_pane:
            return False
        v.state.active_cell = cell
        self._set_active_pane(pane)
        self.sync_current_index()
        v.notify_active_image_changed()
        return True

    def on_label_pressed(self, label) -> bool:
        """クリックされたタイルを active にする。active タイルが変わったら True を返す。"""
        pane = next((p for p in self.viewer.panes if p.image_label is label), None)
        cell = self.cell_of(pane) if pane is not None else None
        return cell is not None and self.set_active_cell(cell)

    def sync_current_index(self):
        """active タイルの画像の index を current_index に入れる。空欄の場合は None。"""
        image_id = self.layout.image_at(self.viewer.state.active_cell)
        self.viewer.state.current_index = self.viewer.image_list.index_of(image_id) if image_id is not None else None

    # --- 表示 ---
    def step(self, delta: int):
        """全タイルの表示位置を delta だけ進める。"""
        if not self.layout.has_visible_images():
            return
        self.layout.step(delta)
        self.viewer.show_current_image()

    def visible_images(self) -> list[tuple[Cell, dict | None]]:
        """表示中のマスと、そこに表示する画像の dict（空欄は None）を行優先で返す。"""
        v = self.viewer
        result = []
        for cell in self.layout.visible_cells():
            image_id = self.layout.image_at(cell)
            idx = v.image_list.index_of(image_id) if image_id is not None else None
            result.append((cell, v.images[idx] if idx is not None else None))
        return result

    def canvas_size(self) -> tuple[int, int] | None:
        """表示中の画像の最大の幅・高さを返す。画像がない場合は None。"""
        sizes = [img["array"].shape[:2] for _, img in self.visible_images() if img is not None]
        if not sizes:
            return None
        return max(w for _, w in sizes), max(h for h, _ in sizes)

    def render(self):
        """全タイルを今の zoom 倍率と表示設定で描き、canvas と scroll 位置を揃える。"""
        v = self.viewer
        scale = v.state.scale
        visible = self.visible_images()
        for cell, img in visible:
            pane = self.pane(cell)
            number = self.layout.tile_number(cell)
            if img is None:
                pane.image_id = None
                pane.image_label.clear()
                pane.title_label.setText(f"T{number}: （なし）")
                pane.title_label.setToolTip("")
                pane.status_label.setText("")
                continue
            pane.image_id = img["id"]
            pane.image_label.set_image(v.display_pixmap(img), scale)
            pane.title_label.setText(f"T{number}: {Path(img['path']).name}")
            pane.title_label.setToolTip(img["path"])
        canvas = self.canvas_size()
        for cell, _ in visible:
            self.pane(cell).image_label.set_canvas_size(canvas, scale)
        self.sync_from(v.active_pane)

    # --- scroll の同期 ---
    def sync_from(self, source: ImagePane):
        """source の scroll 位置を他のタイルに写す。"""
        if self._syncing or not self.active:
            return
        self._syncing = True
        try:
            h = source.scroll_area.horizontalScrollBar().value()
            vv = source.scroll_area.verticalScrollBar().value()
            for pane in self.viewer.panes:
                if pane is not source:
                    pane.scroll_area.horizontalScrollBar().setValue(h)
                    pane.scroll_area.verticalScrollBar().setValue(vv)
        finally:
            self._syncing = False

    # --- 画像の削除 ---
    def remove_images(self, image_ids: list[int]):
        for image_id in image_ids:
            self.layout.remove_image(image_id)
