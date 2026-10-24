"""複数画像比較の 1 枚分の tile widget。"""

import contextlib
from pathlib import Path

import numpy as np
from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from PixelScopeViewer.ui import theme
from PixelScopeViewer.ui.dialogs.display.core.compute import apply_brightness_adjustment

from .tile_image_label import TileImageLabel


class TileWidget(QWidget):
    """ファイル名・pixel 値の表示欄と、scroll 可能な画像を持つ tile。

    Args:
        image_data: 画像の dict。
        parent_dialog: 親の TilingDialog。
        tile_index: grid 内の tile の index。
    """

    activated = Signal(int)  # click された tile の index
    roi_changed = Signal(object)  # [x, y, w, h] または None
    mouse_coords_changed = Signal(object)  # (x, y) または None

    def __init__(self, image_data: dict, parent_dialog, tile_index: int):
        super().__init__()

        self.image_data = image_data
        self.parent_dialog = parent_dialog
        self.tile_index = tile_index
        self.is_active = False

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        # active 状態を示す枠
        self.frame = QFrame()
        self.frame.setFrameShape(QFrame.Box)
        self.frame.setLineWidth(2)
        self._update_frame_style()

        frame_layout = QVBoxLayout(self.frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)

        # 上部の表示欄（左: ファイル名、右: pixel 値）
        status_widget = QWidget()
        status_widget.setMaximumHeight(30)
        status_widget.setStyleSheet(theme.TILE_STATUS_STYLESHEET)
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(4, 4, 4, 4)
        status_layout.setSpacing(8)

        self.filename_label = QLabel("")
        self.filename_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.filename_label.setStyleSheet(theme.TILE_FILENAME_STYLESHEET)
        self.filename_label.setWordWrap(False)
        self.filename_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.filename_label.setMinimumWidth(200)
        status_layout.addWidget(self.filename_label, 1)

        self.pixel_value_label = QLabel("")
        self.pixel_value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.pixel_value_label.setMinimumWidth(100)
        self.pixel_value_label.setStyleSheet(theme.TILE_PIXEL_VALUE_STYLESHEET)
        status_layout.addWidget(self.pixel_value_label, 0)

        frame_layout.addWidget(status_widget)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(False)
        self.scroll_area.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.image_label = TileImageLabel()
        self.image_label.roi_changed.connect(self._on_roi_changed)
        self.image_label.clicked.connect(lambda: self.activated.emit(self.tile_index))
        self.image_label.zoom_requested.connect(self._on_zoom_requested)
        self.image_label.hover_info.connect(self._on_hover_info)
        self.scroll_area.setWidget(self.image_label)
        # 同期のため、どこで wheel が発生しても捕捉する
        self.image_label.installEventFilter(self)
        self.scroll_area.viewport().installEventFilter(self)
        self.scroll_area.installEventFilter(self)
        frame_layout.addWidget(self.scroll_area)

        layout.addWidget(self.frame)

        self.setFocusPolicy(Qt.ClickFocus)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel and (
            obj is self.scroll_area.viewport() or obj is self.scroll_area or obj is self.image_label
        ):
            # Ctrl+wheel は zoom
            if event.modifiers() & Qt.ControlModifier:
                dy = event.pixelDelta().y() if not event.pixelDelta().isNull() else event.angleDelta().y()
                if dy != 0:
                    factor = 2.0 if dy > 0 else 0.5
                    # event の座標は受け取った object 基準なので viewport 座標に変換する
                    event_pos = event.position().toPoint() if hasattr(event, "position") else event.pos()
                    if obj is self.scroll_area.viewport():
                        mouse_pos = event_pos
                    elif obj is self.image_label:
                        mouse_pos = self.image_label.mapTo(self.scroll_area.viewport(), event_pos)
                    elif obj is self.scroll_area:
                        mouse_pos = self.scroll_area.mapTo(self.scroll_area.viewport(), event_pos)
                    else:
                        mouse_pos = event_pos
                    self._on_zoom_requested(factor, mouse_pos)
                    return True
            # Ctrl なしは通常の scroll を行い、その後で他の tile に同期する
            vsb = self.scroll_area.verticalScrollBar()
            hsb = self.scroll_area.horizontalScrollBar()

            old_v = vsb.value() if vsb else 0
            old_h = hsb.value() if hsb else 0

            # scroll area に event を届けるため、ここでは処理済みにしない
            result = False

            # event の処理後に、実際に scroll した場合のみ同期する
            def check_and_sync():
                if vsb and vsb.value() != old_v:
                    with contextlib.suppress(Exception):
                        self.parent_dialog.sync_scroll(self.tile_index, "v", vsb.value())
                if hsb and hsb.value() != old_h:
                    with contextlib.suppress(Exception):
                        self.parent_dialog.sync_scroll(self.tile_index, "h", hsb.value())

            QTimer.singleShot(0, check_and_sync)
            return result
        return super().eventFilter(obj, event)

    def _on_zoom_requested(self, factor: float, mouse_pos=None):
        # 全 tile を同期させるため親 dialog で zoom する
        with contextlib.suppress(Exception):
            self.parent_dialog.adjust_zoom(factor, tile_index=self.tile_index, mouse_pos=mouse_pos)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.activated.emit(self.tile_index)
        super().mousePressEvent(event)

    def set_active(self, active: bool):
        """active 状態を設定する。active な tile のみ ROI を編集できる。"""
        self.is_active = active
        self._update_frame_style()

        self.image_label.set_roi_editable(active)

    def _update_frame_style(self):
        if self.is_active:
            # active は青、非 active は灰色の枠
            self.frame.setStyleSheet(theme.TILE_ACTIVE_FRAME_STYLESHEET)
        else:
            self.frame.setStyleSheet(theme.TILE_INACTIVE_FRAME_STYLESHEET)

    def _on_roi_changed(self, roi_rect):
        self.roi_changed.emit(roi_rect)

    def _on_hover_info(self, ix: int, iy: int, value_text: str):
        # 座標のみ通知し、全 tile の pixel 値の表示は親 dialog で更新する
        if value_text:
            self.mouse_coords_changed.emit((ix, iy))
        else:
            self.mouse_coords_changed.emit(None)

    def set_image(self, array: np.ndarray, gain: float, offset: float, upper_level: float):
        self.image_label.set_image(array, gain, offset, upper_level)

    def update_display(self):
        """親 dialog の brightness を適用して画像とファイル名を表示する。"""
        arr = self.image_data.get("base_array")
        if arr is None:
            return

        if hasattr(self.parent_dialog, "brightness_manager") and self.parent_dialog.brightness_manager:
            brightness_params = self.parent_dialog.brightness_manager.get_brightness_params()
            dtype_group = self.parent_dialog.tile_manager.get_tile_dtype_groups()[self.tile_index]
            params = brightness_params["params_by_dtype"][dtype_group]
            gain = brightness_params["gain"]
        else:
            params = {"offset": 0, "upper_level": 255}
            gain = 1.0

        self.image_label.set_image(arr, gain, params["offset"], params["upper_level"])

        path = self.image_data.get("path", f"Image {self.tile_index + 1}")
        filename = Path(path).name if path else f"Image {self.tile_index + 1}"
        display_text = f"Tile {self.tile_index + 1}: {filename}"
        self.filename_label.setText(display_text)
        self.filename_label.setToolTip(display_text)

    def get_displayed_array(self) -> np.ndarray:
        """brightness を適用した表示用の配列を返す。"""
        arr = self.image_data.get("base_array")
        if hasattr(self.parent_dialog, "brightness_manager") and self.parent_dialog.brightness_manager:
            brightness_params = self.parent_dialog.brightness_manager.get_brightness_params()
            dtype_group = self.parent_dialog.tile_manager.get_tile_dtype_groups()[self.tile_index]
            params = brightness_params["params_by_dtype"][dtype_group]
            gain = brightness_params["gain"]
        else:
            params = {"offset": 0, "upper_level": 255}
            gain = 1.0

        adjusted = apply_brightness_adjustment(
            arr, gain=gain, offset=params["offset"], upper_level=params["upper_level"]
        )
        return adjusted

    def get_base_array(self) -> np.ndarray:
        """brightness 適用前の配列を返す。"""
        return self.image_data.get("base_array")

    def update_status(self, text: str):
        """pixel 値の表示を更新する。"""
        self.pixel_value_label.setText(text)

    def set_roi(self, roi_rect: list | None):
        self.image_label.set_roi(roi_rect)

    def set_roi_from_image_coords(self, roi_rect, is_active: bool):
        """画像座標の QRect（または None）を ROI に設定する。"""
        if roi_rect and not roi_rect.isEmpty():
            self.image_label.set_roi([roi_rect.x(), roi_rect.y(), roi_rect.width(), roi_rect.height()])
        else:
            self.image_label.set_roi(None)

    def clear_roi(self):
        self.image_label.clear_roi()

    def select_all_roi(self, array_shape: tuple):
        """画像全体を ROI にする。"""
        h, w = array_shape[:2]
        self.image_label.set_roi([0, 0, w, h])

    def set_zoom(self, factor: float):
        self.image_label.set_zoom(factor)
