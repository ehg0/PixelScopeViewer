"""ImageViewer のタイル比較モード（切り替え・タイルの表示・scroll の同期・active タイル）。"""

from dataclasses import replace

from PySide6.QtCore import QPoint, QTimer

from PixelScopeViewer.core.brightness import BrightnessParams, determine_dtype_group
from PixelScopeViewer.core.pixel import pixel_value_text
from PixelScopeViewer.core.tile_layout import Cell, TileLayout
from PixelScopeViewer.ui.common import defaults
from PixelScopeViewer.ui.viewer.state import TILE_BRIGHTNESS_KEY
from PixelScopeViewer.ui.viewer.widgets import ImagePane


class TileModeManager:
    """メイン画面をグリッドに分割し、各マスの画像を同じ zoom・表示位置・ROI で表示する。

    pane はマスごとに 1 度だけ作り、(0, 0) のマスは 1 枚表示の pane と共有する。
    active タイルの画像の index を viewer.state.current_index に入れ、1 枚分の情報を出す機能はその画像を対象にする。
    """

    def __init__(self, viewer):
        self.viewer = viewer
        self._panes: dict[Cell, ImagePane] = {(0, 0): viewer.panes[0]}
        self._syncing = False
        # brightness の slider 操作中は、active 以外のタイルの描き直しを操作が止まるまで待つ
        self._deferred_render = QTimer()
        self._deferred_render.setSingleShot(True)
        self._deferred_render.setInterval(defaults.TILE_BRIGHTNESS_DEBOUNCE_MS)
        self._deferred_render.timeout.connect(self.render)

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
            self._show_with_tile_brightness()
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
        self._show_with_tile_brightness()
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
        self._arrange([(0, 0)], tile_mode=False)
        single = self._panes[(0, 0)]
        single.image_label.set_canvas_size(None)
        v.active_pane = single
        if st.current_index is None and v.images:
            st.current_index = 0
        self._show_with_tile_brightness()
        if center is not None and v.has_image():
            v.zoom_manager.set_zoom_at_coords(st.scale, center)

    def _show_with_tile_brightness(self):
        """表示設定 dialog の brightness をモードに合わせてから、全タイル（1 枚表示では画像）を 1 回だけ描く。"""
        v = self.viewer
        with v.brightness_manager.render_held():
            v.brightness_manager.sync_tile_mode()
        v.show_current_image()

    def registered_dtype_groups(self) -> list[str]:
        """表示中のマスに登録されている画像の dtype の group を返す。先頭は最初のタイルの画像の dtype。"""
        find = self.viewer.image_list.find
        first = self._first_visible_image()
        groups = [determine_dtype_group(first["array"])] if first is not None else []
        for cell in self.layout.visible_cells():
            for image_id in self.layout.stack(cell):
                img = find(image_id)
                if img is not None and (g := determine_dtype_group(img["array"])) not in groups:
                    groups.append(g)
        return groups

    def _first_visible_image(self) -> dict | None:
        find = self.viewer.image_list.find
        return next((img for i in self.layout.visible_image_ids() if (img := find(i)) is not None), None)

    # --- グリッド ---
    def apply_layout(self):
        """表示するマスの pane をグリッドに並べ、active タイルを決める。"""
        v = self.viewer
        self._arrange(self.layout.visible_cells(), tile_mode=True)
        if not self.layout.is_visible(v.state.active_cell):
            v.state.active_cell = (0, 0)
        self._set_active_pane(self.pane(v.state.active_cell))

    def _arrange(self, cells: list[Cell], tile_mode: bool):
        """cells の pane だけをグリッドに並べて viewer.panes にする。他の pane は隠す。"""
        grid = self.viewer.pane_grid
        for pane in list(self._panes.values()):
            grid.removeWidget(pane)
            pane.hide()
        for cell in cells:
            pane = self.pane(cell)
            pane.set_tile_mode(tile_mode)
            grid.addWidget(pane, *cell)
            pane.show()
        rows = max(r for r, _ in cells) + 1
        cols = max(c for _, c in cells) + 1
        for r in range(self.layout.max_rows):
            grid.setRowStretch(r, 1 if r < rows else 0)
        for c in range(self.layout.max_cols):
            grid.setColumnStretch(c, 1 if c < cols else 0)
        self.viewer.panes = [self.pane(cell) for cell in cells]

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
        self.viewer.state.current_index = self.viewer.image_list.index_of(image_id)

    # --- 表示 ---
    def step(self, delta: int):
        """全タイルの表示位置を delta だけ進める。"""
        if not self.layout.has_visible_images():
            return
        self.layout.step(delta)
        self.viewer.show_current_image()

    def visible_images(self) -> list[tuple[Cell, dict | None]]:
        """表示中のマスと、そこに表示する画像の dict（空欄は None）を行優先で返す。"""
        find = self.viewer.image_list.find
        return [(cell, find(self.layout.image_at(cell))) for cell in self.layout.visible_cells()]

    def canvas_size(self) -> tuple[int, int] | None:
        """表示中の画像の最大の幅・高さを返す。画像がない場合は None。"""
        sizes = [img["array"].shape[:2] for _, img in self.visible_images() if img is not None]
        if not sizes:
            return None
        return max(w for _, w in sizes), max(h for h, _ in sizes)

    def render_active_first(self):
        """active タイルだけをすぐに描き直し、残りのタイルは少し待ってからまとめて描き直す。"""
        v = self.viewer
        img = next((img for cell, img in self.visible_images() if cell == v.state.active_cell), None)
        if img is not None:
            v.active_pane.image_label.set_image(v.renderer.pixmap(img), v.state.scale)
        self._deferred_render.start()

    def render(self):
        """全タイルを今の zoom 倍率と表示設定で描き、canvas と scroll 位置を揃える。"""
        self._deferred_render.stop()
        if not self.active:
            return
        v = self.viewer
        scale = v.state.scale
        visible = self.visible_images()
        for cell, img in visible:
            pixmap = v.renderer.pixmap(img) if img is not None else None
            self.pane(cell).show_image(img, pixmap, scale, tile_number=self.layout.tile_number(cell))
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

    # --- マウス位置の pixel 値 ---
    def show_pixel_values(self, pos: QPoint | None) -> tuple[int, int] | None:
        """マウス位置（widget 座標）の画像座標を求め、各タイルのステータス行に同じ座標の pixel 値を出す。

        Returns:
            canvas の範囲内の画像座標。範囲外や pos が None の場合は None。
        """
        canvas = self.canvas_size()
        point = None
        if pos is not None and canvas is not None:
            s = self.viewer.state.scale if self.viewer.state.scale > 0 else 1.0
            ix, iy = int(pos.x() / s), int(pos.y() / s)
            if 0 <= ix < canvas[0] and 0 <= iy < canvas[1]:
                point = (ix, iy)
        for cell, img in self.visible_images():
            text = ""
            if point is not None and img is not None:
                val = pixel_value_text(img.get("base_array", img.get("array")), *point)
                text = f"val={val}" if val is not None else ""
            self.pane(cell).status_label.setText(text)
        return point
