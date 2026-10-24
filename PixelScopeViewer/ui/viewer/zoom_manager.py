"""ImageViewer の zoom と表示位置の制御。"""

import numpy as np

from PixelScopeViewer.core.constants import MAX_ZOOM_SCALE, MIN_ZOOM_SCALE


class ZoomManager:
    """zoom 時に注目点の表示位置を保つよう scroll を調整する。"""

    def __init__(self, viewer):
        self.viewer = viewer

    def apply_zoom_and_update_display(self, scale: float):
        self.viewer.state.scale = scale
        arr = self.viewer.images[self.viewer.state.current_index]["array"]
        self.viewer.display_image(arr)

    def calculate_viewport_center_in_image_coords(self) -> tuple[float, float]:
        """viewport の中心を画像座標で返す。"""
        scroll_area = self.viewer.scroll_area
        old_h_scroll = scroll_area.horizontalScrollBar().value()
        old_v_scroll = scroll_area.verticalScrollBar().value()
        viewport_width = scroll_area.viewport().width()
        viewport_height = scroll_area.viewport().height()

        old_center_x = old_h_scroll + viewport_width / 2.0
        old_center_y = old_v_scroll + viewport_height / 2.0

        old_scale = self.viewer.state.scale
        if old_scale > 0:
            img_center_x = old_center_x / old_scale
            img_center_y = old_center_y / old_scale
        else:
            img_center_x = old_center_x
            img_center_y = old_center_y

        return (img_center_x, img_center_y)

    def set_scroll_to_keep_image_point_at_position(
        self, img_coords: tuple[float, float], target_pos: tuple[float, float]
    ):
        """画像座標 img_coords が viewport 上の target_pos に表示されるよう scroll する。"""
        img_x, img_y = img_coords
        target_x, target_y = target_pos

        new_widget_x = img_x * self.viewer.state.scale
        new_widget_y = img_y * self.viewer.state.scale

        scroll_area = self.viewer.scroll_area
        new_h_scroll = int(new_widget_x - target_x)
        new_v_scroll = int(new_widget_y - target_y)

        scroll_area.horizontalScrollBar().setValue(new_h_scroll)
        scroll_area.verticalScrollBar().setValue(new_v_scroll)

    def set_zoom(self, scale: float):
        """viewport の中心を保ったまま zoom する。"""
        if self.viewer.state.current_index is None:
            self.viewer.state.scale = scale
            return

        img_center = self.calculate_viewport_center_in_image_coords()

        self.apply_zoom_and_update_display(scale)

        scroll_area = self.viewer.scroll_area
        viewport_width = scroll_area.viewport().width()
        viewport_height = scroll_area.viewport().height()
        center_pos = (viewport_width / 2.0, viewport_height / 2.0)

        self.set_scroll_to_keep_image_point_at_position(img_center, center_pos)

        self.viewer.scale_changed.emit()

    def set_zoom_at_status_coords(self, scale: float):
        """status bar に表示中のマウス座標を viewport の中心にして zoom する。

        マウス座標がない場合は viewport の中心を保って zoom する。
        """
        if self.viewer.state.current_index is None:
            self.viewer.state.scale = scale
            return

        if self.viewer.current_mouse_image_coords is None:
            self.set_zoom(scale)
            return

        self.apply_zoom_and_update_display(scale)

        scroll_area = self.viewer.scroll_area
        viewport_width = scroll_area.viewport().width()
        viewport_height = scroll_area.viewport().height()
        center_pos = (viewport_width / 2.0, viewport_height / 2.0)

        self.set_scroll_to_keep_image_point_at_position(self.viewer.current_mouse_image_coords, center_pos)

        self.viewer.scale_changed.emit()

    def set_zoom_at_coords(self, scale: float, image_coords: tuple[float, float]):
        """画像座標 image_coords を viewport の中心にして zoom する。"""
        if self.viewer.state.current_index is None:
            self.viewer.state.scale = scale
            return

        self.apply_zoom_and_update_display(scale)

        scroll_area = self.viewer.scroll_area
        viewport_width = scroll_area.viewport().width()
        viewport_height = scroll_area.viewport().height()
        center_pos = (viewport_width / 2.0, viewport_height / 2.0)

        self.set_scroll_to_keep_image_point_at_position(image_coords, center_pos)

        self.viewer.scale_changed.emit()

    def fit_to_window(self):
        """画像全体が window に収まる倍率のうち、最も近い 2 の累乗の倍率で表示する。"""
        if self.viewer.state.current_index is None:
            return
        img = self.viewer.images[self.viewer.state.current_index]["array"]
        h, w = img.shape[:2]
        viewport = self.viewer.scroll_area.viewport()
        vh = viewport.height()
        wh = viewport.width()
        scale_h = vh / h
        scale_w = wh / w
        fit_scale = min(scale_h, scale_w)
        fit_scale = max(MIN_ZOOM_SCALE, min(MAX_ZOOM_SCALE, fit_scale))
        power = round(np.log2(fit_scale))
        snapped_scale = 2.0**power
        self.set_zoom(snapped_scale)

    def toggle_fit_zoom(self):
        """window に合わせた倍率と、直前の倍率・表示位置を切り替える。"""
        if self.viewer.state.current_index is None:
            return
        if (
            self.viewer.state.fit_zoom_scale is not None
            and abs(self.viewer.state.scale - self.viewer.state.fit_zoom_scale) < 1e-6
        ):
            # fit 中なので元の倍率と中心に戻す
            if self.viewer.state.original_center_coords is not None:
                self.set_zoom_at_coords(self.viewer.state.original_zoom_scale, self.viewer.state.original_center_coords)
            else:
                self.set_zoom(self.viewer.state.original_zoom_scale)
        else:
            # 現在の倍率と中心を記録してから fit する
            self.viewer.state.original_zoom_scale = self.viewer.state.scale
            self.viewer.state.original_center_coords = self.calculate_viewport_center_in_image_coords()
            self.fit_to_window()
            self.viewer.state.fit_zoom_scale = self.viewer.state.scale
