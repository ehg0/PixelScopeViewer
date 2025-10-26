"""Zoom and viewport management for ImageViewer.

This module handles all zoom-related operations including:
- Setting zoom scale with viewport center preservation
- Zooming at specific image coordinates
- Fit-to-window functionality
- Zoom toggle between fit and previous zoom level
"""

import numpy as np


class ZoomManager:
    """Manages zoom and viewport operations for the image viewer.

    This class handles zoom calculations and viewport positioning to maintain
    visual continuity during zoom operations.
    """

    def __init__(self, viewer):
        """Initialize zoom manager.

        Args:
            viewer: ImageViewer instance
        """
        self.viewer = viewer

    def apply_zoom_and_update_display(self, scale: float):
        """Apply zoom scale and update display. Common logic for all zoom methods.

        Args:
            scale: New zoom scale factor (1.0 = original size)
        """
        self.viewer.scale = scale
        arr = self.viewer.images[self.viewer.current_index]["array"]
        self.viewer.display_image(arr)

    def calculate_viewport_center_in_image_coords(self) -> tuple[float, float]:
        """Calculate current viewport center in image coordinates.

        Returns:
            (img_x, img_y) tuple of center point in image coordinates
        """
        scroll_area = self.viewer.scroll_area
        old_h_scroll = scroll_area.horizontalScrollBar().value()
        old_v_scroll = scroll_area.verticalScrollBar().value()
        viewport_width = scroll_area.viewport().width()
        viewport_height = scroll_area.viewport().height()

        # Calculate center point in widget coordinates
        old_center_x = old_h_scroll + viewport_width / 2.0
        old_center_y = old_v_scroll + viewport_height / 2.0

        # Convert to image coordinates (independent of scale)
        old_scale = self.viewer.scale
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
        """Set scroll position to keep an image point at a target widget position.

        Args:
            img_coords: (x, y) in image coordinates
            target_pos: (x, y) in widget coordinates where the image point should appear
        """
        img_x, img_y = img_coords
        target_x, target_y = target_pos

        # Calculate where the image point appears in the new scale
        new_widget_x = img_x * self.viewer.scale
        new_widget_y = img_y * self.viewer.scale

        # Calculate required scroll position
        scroll_area = self.viewer.scroll_area
        new_h_scroll = int(new_widget_x - target_x)
        new_v_scroll = int(new_widget_y - target_y)

        # Apply new scroll position
        scroll_area.horizontalScrollBar().setValue(new_h_scroll)
        scroll_area.verticalScrollBar().setValue(new_v_scroll)

    def set_zoom(self, scale: float):
        """ズーム倍率を設定し、可視領域の中心位置を維持します。

        パラメータ:
            scale: 新しい倍率(1.0 が原寸)

        このメソッドは表示中の画像がない場合は単に scale を設定して終了します。
        """
        if self.viewer.current_index is None:
            self.viewer.scale = scale
            return

        # Get current viewport center in image coordinates
        img_center = self.calculate_viewport_center_in_image_coords()

        # Apply new zoom
        self.apply_zoom_and_update_display(scale)

        # Calculate viewport center position for target
        scroll_area = self.viewer.scroll_area
        viewport_width = scroll_area.viewport().width()
        viewport_height = scroll_area.viewport().height()
        center_pos = (viewport_width / 2.0, viewport_height / 2.0)

        # Keep center point at viewport center
        self.set_scroll_to_keep_image_point_at_position(img_center, center_pos)

        self.viewer.scale_changed.emit()

    def set_zoom_at_status_coords(self, scale: float):
        """ステータスバーに表示している座標(マウス位置)をビュー中心に固定してズームします。

        マウス位置が未取得(None)の場合は通常の center ベースの set_zoom にフォールバックします。
        """
        if self.viewer.current_index is None:
            self.viewer.scale = scale
            return

        if self.viewer.current_mouse_image_coords is None:
            # If no valid mouse coordinates, fall back to center zoom
            self.set_zoom(scale)
            return

        # Apply new zoom
        self.apply_zoom_and_update_display(scale)

        # Get viewport center for positioning
        scroll_area = self.viewer.scroll_area
        viewport_width = scroll_area.viewport().width()
        viewport_height = scroll_area.viewport().height()
        center_pos = (viewport_width / 2.0, viewport_height / 2.0)

        # Place the status coordinates at the center of the viewport
        self.set_scroll_to_keep_image_point_at_position(self.viewer.current_mouse_image_coords, center_pos)

        self.viewer.scale_changed.emit()

    def set_zoom_at_coords(self, scale: float, image_coords: tuple[float, float]):
        """指定した画像座標をビューポート中心に維持してズーム倍率を設定します。

        パラメータ:
            scale: 新しい倍率(1.0 が原寸)
            image_coords: (x, y) 維持する画像座標

        このメソッドは表示中の画像がない場合は単に scale を設定して終了します。
        """
        if self.viewer.current_index is None:
            self.viewer.scale = scale
            return

        # Apply new zoom
        self.apply_zoom_and_update_display(scale)

        # Get viewport center for positioning
        scroll_area = self.viewer.scroll_area
        viewport_width = scroll_area.viewport().width()
        viewport_height = scroll_area.viewport().height()
        center_pos = (viewport_width / 2.0, viewport_height / 2.0)

        # Place the image_coords at the center of the viewport
        self.set_scroll_to_keep_image_point_at_position(image_coords, center_pos)

        self.viewer.scale_changed.emit()

    def fit_to_window(self):
        """画像をウィンドウにフィットさせるズーム倍率を設定します。

        画像のアスペクト比を維持して、ウィンドウのサイズに合わせてスケールを計算し、
        最も近いバイナリ倍率(2の累乗)にスナップします。
        """
        if self.viewer.current_index is None:
            return
        img = self.viewer.images[self.viewer.current_index]["array"]
        h, w = img.shape[:2]
        viewport = self.viewer.scroll_area.viewport()
        vh = viewport.height()
        wh = viewport.width()
        scale_h = vh / h
        scale_w = wh / w
        fit_scale = min(scale_h, scale_w)
        # Clamp to valid zoom range
        fit_scale = max(0.125, min(128.0, fit_scale))
        # Snap to nearest power of 2
        power = round(np.log2(fit_scale))
        snapped_scale = 2.0**power
        self.set_zoom(snapped_scale)

    def toggle_fit_zoom(self):
        """Fitと直前の拡大率をトグルします。

        現在のスケールがfitスケールに近い場合は直前の拡大率に戻し、
        そうでなければ現在のスケールを記憶してfitにします。
        """
        if self.viewer.current_index is None:
            return
        if self.viewer.fit_zoom_scale is not None and abs(self.viewer.scale - self.viewer.fit_zoom_scale) < 1e-6:
            # Currently at fit zoom, go back to original zoom, maintaining the original center
            if self.viewer.original_center_coords is not None:
                self.set_zoom_at_coords(self.viewer.original_zoom_scale, self.viewer.original_center_coords)
            else:
                self.set_zoom(self.viewer.original_zoom_scale)
        else:
            # Not at fit zoom, remember current center and scale as original, go to fit
            self.viewer.original_zoom_scale = self.viewer.scale
            self.viewer.original_center_coords = self.calculate_viewport_center_in_image_coords()
            self.fit_to_window()
            self.viewer.fit_zoom_scale = self.viewer.scale
