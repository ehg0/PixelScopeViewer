"""ImageViewer の status bar と title bar の更新。"""

from pathlib import Path

import numpy as np
from PySide6.QtWidgets import QHBoxLayout, QLabel, QStatusBar, QWidget

from PixelScopeViewer.core.image_io import format_file_size
from PixelScopeViewer.core.pixel import pixel_value_text


class StatusUpdater:
    """ImageViewer の status bar を作り、viewer の状態を status bar と title bar に表示する。

    status bar は左にマウス位置の pixel 値と ROI、右に brightness と zoom 倍率を並べる。
    """

    def __init__(self, viewer):
        self.viewer = viewer
        self.pixel_label = QLabel()
        self.roi_label = QLabel()
        self.brightness_label = QLabel()
        self.scale_label = QLabel()

        status = QStatusBar()
        viewer.setStatusBar(status)
        status.setStyleSheet("font-size: 11pt;")
        status.addWidget(self._group(self.pixel_label, QLabel("|"), self.roi_label))
        status.addPermanentWidget(self._group(QLabel("|"), self.brightness_label, QLabel("|"), self.scale_label))

    @staticmethod
    def _group(*widgets) -> QWidget:
        """widget を左右に余白を取って横に並べる。"""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(15, 0, 15, 0)
        layout.setSpacing(8)
        for w in widgets:
            layout.addWidget(w)
        return container

    def _image_point(self, pos) -> tuple[int, int]:
        s = self.viewer.state.scale if self.viewer.state.scale > 0 else 1.0
        return int(pos.x() / s), int(pos.y() / s)

    def update_mouse_status(self, pos):
        """マウス位置（widget 座標）の pixel 値を表示する。pos が None の場合は消す。"""
        if pos is None or self.viewer.state.current_index is None or not self.viewer.images:
            self.pixel_label.setText("")
            self.viewer.current_mouse_image_coords = None
            return
        img = self.viewer.images[self.viewer.state.current_index]
        # brightness 調整前の base_array の値を表示する
        ix, iy = self._image_point(pos)
        val_str = pixel_value_text(img.get("base_array", img.get("array")), ix, iy)
        if val_str is None:
            self.pixel_label.setText("")
            self.viewer.current_mouse_image_coords = None
            return
        self.pixel_label.setText(f"x={ix} y={iy} val={val_str}")
        # zoom の中心として使う
        self.viewer.current_mouse_image_coords = (ix, iy)

    def show_mouse_point(self, point: tuple[int, int] | None):
        """マウス位置の画像座標だけを表示する（タイル比較モード）。None の場合は消す。"""
        self.pixel_label.setText(f"x={point[0]} y={point[1]}" if point is not None else "")

    def update_roi_status(self) -> None:
        """ROI の範囲を表示する。"""
        if self.viewer.state.current_index is None or not self.viewer.images:
            self.roi_label.setText("")
            return
        if self.viewer.state.roi and not self.viewer.state.roi.isEmpty():
            r = self.viewer.state.roi
            x0, y0 = r.x(), r.y()
            x1, y1 = x0 + r.width() - 1, y0 + r.height() - 1
            self.roi_label.setText(f"({x0}, {y0}) - ({x1}, {y1}), w: {r.width()}, h: {r.height()}")
        else:
            self.roi_label.setText("")

    def update_status(self):
        """title bar（ファイル名・サイズ・番号）と zoom 倍率、brightness を更新する。"""
        state = self.viewer.state
        if state.tile_mode:
            layout = state.tile_layout
            count = layout.frame_count()
            frame = f" [{layout.frame + 1}/{count}]" if count else ""
            self.viewer.setWindowTitle(f"PixelScopeViewer — タイル比較 {layout.rows}×{layout.cols}{frame}")
            self.scale_label.setText(f"Scale: {state.scale:.2f}x")
            self.update_brightness_status()
            return
        if self.viewer.state.current_index is None:
            self.viewer.setWindowTitle("PixelScopeViewer")
            self.scale_label.setText(f"Scale: {self.viewer.state.scale:.2f}x")
            self.brightness_label.setText("")
            return
        p = self.viewer.images[self.viewer.state.current_index]["path"]

        # 長いパスは途中を省略する
        p_path = Path(p)
        parts = p_path.parts
        if len(parts) > 3:
            host_root = parts[0].replace("\\", "/").rstrip("/")
            filename = f"{host_root}/.../{p_path.parent.name}/{p_path.name}"
        else:
            filename = f"{p_path.parent.name}/{p_path.name}"
        img = self.viewer.images[self.viewer.state.current_index]
        arr = img.get("base_array", img.get("array"))
        if arr.ndim == 2:
            h, w = arr.shape
            c = 1
        else:
            h, w, c = arr.shape[:3]

        try:
            file_size_str = format_file_size(Path(p).stat().st_size, sep="")
        except OSError:
            file_size_str = ""

        size_part = f" ({file_size_str})" if file_size_str else ""
        title = (
            f"[{self.viewer.state.current_index + 1}/{len(self.viewer.images)}]  {filename}{size_part} — {w}×{h}, {c}ch"
        )
        self.viewer.setWindowTitle(title)

        self.scale_label.setText(f"Scale: {self.viewer.state.scale:.2f}x")

        self.update_brightness_status()

    def update_brightness_status(self):
        """brightness の offset/gain/upper level を表示する。gain は値が小さいほど小数桁を増やす。"""
        b = self.viewer.state.brightness
        offset_str = str(b.offset) if isinstance(b.offset, (int, np.integer)) else f"{b.offset:.1f}"
        upper_str = str(b.upper_level) if isinstance(b.upper_level, (int, np.integer)) else f"{b.upper_level:.1f}"
        # 小さい gain ほど小数の桁を増やす
        if b.gain < 0.01:
            gain_str = f"{b.gain:.6f}"
        elif b.gain < 0.1:
            gain_str = f"{b.gain:.5f}"
        elif b.gain >= 100:
            gain_str = f"{b.gain:.1f}"
        else:
            gain_str = f"{b.gain:.2f}"
        self.brightness_label.setText(f"Offset: {offset_str}, Gain: {gain_str}, Upper: {upper_str}")
