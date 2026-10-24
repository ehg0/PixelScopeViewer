"""複数画像比較の ROI 管理。"""

import numpy as np
from PySide6.QtCore import QRect, Signal
from PySide6.QtGui import QGuiApplication

from PixelScopeViewer.ui.common.qt_image import numpy_to_qimage


class ROIManager:
    """全 tile 共通の ROI と、ROI 画像のコピーを管理する。

    Args:
        tiles: TileWidget のリスト。
        get_active_tile_index_func: active な tile の index を返す関数。
        common_roi_changed_signal: ROI の変更時に emit する signal。
    """

    def __init__(self, tiles: list, get_active_tile_index_func, common_roi_changed_signal: Signal):
        self.tiles = tiles
        self.get_active_tile_index = get_active_tile_index_func
        self.common_roi_changed = common_roi_changed_signal
        self.common_roi_rect: QRect | None = None

    def on_tile_roi_changed_list(self, roi_rect):
        """[x, y, w, h] 形式（または None）の ROI を共通 ROI にする。"""
        if roi_rect:
            self.common_roi_rect = QRect(roi_rect[0], roi_rect[1], roi_rect[2], roi_rect[3])
        else:
            self.common_roi_rect = None

        if self.common_roi_rect:
            self.common_roi_changed.emit(self.common_roi_rect)

    def sync_roi_to_all_tiles(self, roi_rect: QRect):
        for i, tile in enumerate(self.tiles):
            is_active = i == self.get_active_tile_index()
            tile.set_roi_from_image_coords(roi_rect, is_active)

    def select_all_roi(self):
        """active な tile の画像全体を ROI にする。"""
        if not self.tiles or self.get_active_tile_index() >= len(self.tiles):
            return

        active_tile = self.tiles[self.get_active_tile_index()]
        arr = active_tile.image_data["base_array"]
        h, w = arr.shape[:2]

        full_roi = QRect(0, 0, w, h)
        self.common_roi_rect = full_roi
        self.common_roi_changed.emit(full_roi)

    def clear_roi(self):
        self.common_roi_rect = None
        self.common_roi_changed.emit(QRect())

    def copy_active_tile_roi(self):
        """active な tile の ROI（ROI がなければ全体）の表示画像を clipboard にコピーする。"""
        if not self.tiles or self.get_active_tile_index() >= len(self.tiles):
            return

        active_tile = self.tiles[self.get_active_tile_index()]
        roi_rect = self.common_roi_rect

        arr = active_tile.get_displayed_array()

        if roi_rect and not roi_rect.isEmpty():
            x, y, w, h = roi_rect.x(), roi_rect.y(), roi_rect.width(), roi_rect.height()
            h_arr, w_arr = arr.shape[:2]

            if x < w_arr and y < h_arr:
                x2 = min(x + w, w_arr)
                y2 = min(y + h, h_arr)
                sub_arr = arr[y:y2, x:x2]
                qimg = numpy_to_qimage(sub_arr)
            else:
                qimg = None
        else:
            qimg = numpy_to_qimage(arr)

        if qimg and not qimg.isNull():
            QGuiApplication.clipboard().setImage(qimg)

    def copy_all_tiles_roi_as_grid(self, grid_size: tuple[int, int]):
        """全 tile の ROI の表示画像を grid に並べて clipboard にコピーする。

        Args:
            grid_size: (行数, 列数)。
        """
        if not self.tiles:
            return

        roi_rect = self.common_roi_rect
        if not roi_rect or roi_rect.isEmpty():
            return

        x, y, w, h = roi_rect.x(), roi_rect.y(), roi_rect.width(), roi_rect.height()
        rows, cols = grid_size

        roi_images = []
        for tile in self.tiles:
            arr = tile.get_displayed_array()
            if arr is None:
                continue

            h_arr, w_arr = arr.shape[:2]
            if x < w_arr and y < h_arr:
                x2 = min(x + w, w_arr)
                y2 = min(y + h, h_arr)
                sub_arr = arr[y:y2, x:x2]
                roi_images.append(sub_arr)
            else:
                # ROI が範囲外の tile は空ける
                roi_images.append(None)

        if not roi_images or all(img is None for img in roi_images):
            return

        # 最初の有効な ROI 画像のサイズを 1 マスのサイズにする
        roi_h, roi_w = h, w
        for img in roi_images:
            if img is not None:
                roi_h, roi_w = img.shape[:2]
                break

        is_color = False
        num_channels = 1
        for img in roi_images:
            if img is not None and len(img.shape) == 3:
                is_color = True
                num_channels = img.shape[2]
                break

        output_h = rows * roi_h
        output_w = cols * roi_w
        if is_color:
            output_array = np.zeros(
                (output_h, output_w, num_channels), dtype=roi_images[0].dtype if roi_images[0] is not None else np.uint8
            )
        else:
            output_array = np.zeros(
                (output_h, output_w), dtype=roi_images[0].dtype if roi_images[0] is not None else np.uint8
            )

        for i, img in enumerate(roi_images):
            if img is None:
                continue

            row = i // cols
            col = i % cols
            y_start = row * roi_h
            x_start = col * roi_w

            img_h, img_w = img.shape[:2]
            y_end = min(y_start + img_h, output_h)
            x_end = min(x_start + img_w, output_w)

            if is_color and len(img.shape) == 2:
                img = np.stack([img] * num_channels, axis=2)
            elif is_color and img.shape[2] != num_channels:
                # channel 数が異なる tile は grayscale にして揃える
                gray = img.mean(axis=2).astype(img.dtype)
                img = np.stack([gray] * num_channels, axis=2)
            elif not is_color and len(img.shape) == 3:
                img = img[:, :, 0]

            output_array[y_start:y_end, x_start:x_end] = img[: y_end - y_start, : x_end - x_start]

        qimg = numpy_to_qimage(output_array)
        if qimg and not qimg.isNull():
            QGuiApplication.clipboard().setImage(qimg)

    def get_roi_status(self) -> str:
        """status bar に表示する ROI の文字列を返す。"""
        if self.common_roi_rect and not self.common_roi_rect.isEmpty():
            r = self.common_roi_rect
            x0, y0 = r.x(), r.y()
            x1, y1 = x0 + r.width() - 1, y0 + r.height() - 1
            return f" | ({x0}, {y0}) - ({x1}, {y1}), w: {r.width()}, h: {r.height()}"
        return ""
