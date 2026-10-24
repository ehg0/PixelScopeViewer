"""ImageViewer の status bar と title bar の更新。"""

from pathlib import Path

import numpy as np


class StatusUpdater:
    """ImageViewer の状態を status bar と title bar に表示する。"""

    def __init__(self, viewer):
        self.viewer = viewer

    def update_mouse_status(self, pos):
        """マウス位置（widget 座標）の pixel 値を表示する。"""
        if self.viewer.current_index is None or not self.viewer.images:
            self.viewer.status_pixel.setText("")
            self.viewer.current_mouse_image_coords = None
            return
        img = self.viewer.images[self.viewer.current_index]
        # brightness 調整前の base_array の値を表示する
        arr = img.get("base_array", img.get("array"))
        s = self.viewer.scale if self.viewer.scale > 0 else 1.0
        ix = int(pos.x() / s)
        iy = int(pos.y() / s)
        h, w = arr.shape[:2]
        if 0 <= iy < h and 0 <= ix < w:
            v = arr[iy, ix]

            def _format_scalar(x, dtype):
                try:
                    if np.issubdtype(dtype, np.floating):
                        xv = float(x)
                        return f"{xv:.3f}"
                    else:
                        return str(int(x))
                except Exception:
                    return str(x)

            if np.ndim(v) == 0:
                val_str = _format_scalar(v, arr.dtype)
            else:
                vals = [_format_scalar(x, arr.dtype) for x in np.ravel(v)]
                val_str = "(" + ",".join(vals) + ")"

            self.viewer.status_pixel.setText(f"x={ix} y={iy} val={val_str}")
            # zoom の中心として使う
            self.viewer.current_mouse_image_coords = (ix, iy)
        else:
            self.viewer.status_pixel.setText("")
            self.viewer.current_mouse_image_coords = None

    def update_roi_status(self) -> None:
        """ROI の範囲を表示する。"""
        if self.viewer.current_index is None or not self.viewer.images:
            self.viewer.status_roi_area.setText("")
            return
        if self.viewer.current_roi_rect and not self.viewer.current_roi_rect.isEmpty():
            r = self.viewer.current_roi_rect
            x0, y0 = r.x(), r.y()
            x1, y1 = x0 + r.width() - 1, y0 + r.height() - 1
            self.viewer.status_roi_area.setText(f"({x0}, {y0}) - ({x1}, {y1}), w: {r.width()}, h: {r.height()}")
        else:
            self.viewer.status_roi_area.setText("")

    def update_status(self):
        """title bar（ファイル名・サイズ・番号）と zoom 倍率、brightness を更新する。"""
        if self.viewer.current_index is None:
            self.viewer.setWindowTitle("PixelScopeViewer")
            self.viewer.status_scale.setText(f"Scale: {self.viewer.scale:.2f}x")
            self.viewer.status_brightness.setText("")
            return
        p = self.viewer.images[self.viewer.current_index]["path"]

        # 長いパスは途中を省略する
        p_path = Path(p)
        parts = p_path.parts
        if len(parts) > 3:
            host_root = parts[0].replace("\\", "/").rstrip("/")
            filename = f"{host_root}/.../{p_path.parent.name}/{p_path.name}"
        else:
            filename = f"{p_path.parent.name}/{p_path.name}"
        img = self.viewer.images[self.viewer.current_index]
        arr = img.get("base_array", img.get("array"))
        if arr.ndim == 2:
            h, w = arr.shape
            c = 1
        else:
            h, w, c = arr.shape[:3]

        file_size_str = ""
        try:
            file_size = Path(p).stat().st_size
            if file_size < 1024:
                file_size_str = f"{file_size}B"
            elif file_size < 1024 * 1024:
                file_size_str = f"{file_size / 1024:.1f}KB"
            elif file_size < 1024 * 1024 * 1024:
                file_size_str = f"{file_size / (1024 * 1024):.1f}MB"
            else:
                file_size_str = f"{file_size / (1024 * 1024 * 1024):.2f}GB"
        except Exception:
            file_size_str = ""

        size_part = f" ({file_size_str})" if file_size_str else ""
        title = f"[{self.viewer.current_index + 1}/{len(self.viewer.images)}]  {filename}{size_part} — {w}×{h}, {c}ch"
        self.viewer.setWindowTitle(title)

        try:
            self.viewer.status_scale.setText(f"Scale: {self.viewer.scale:.2f}x")
        except Exception:
            self.viewer.status_scale.setText("")

        self.update_brightness_status()

    def update_brightness_status(self):
        """brightness の offset/gain/upper level を表示する。gain は値が小さいほど小数桁を増やす。"""
        try:
            if isinstance(self.viewer.brightness_offset, (int, np.integer)):
                offset_str = str(self.viewer.brightness_offset)
            else:
                offset_str = f"{self.viewer.brightness_offset:.1f}"

            if self.viewer.brightness_gain < 0.01:
                gain_str = f"{self.viewer.brightness_gain:.6f}"
            elif self.viewer.brightness_gain < 0.1:
                gain_str = f"{self.viewer.brightness_gain:.5f}"
            elif self.viewer.brightness_gain >= 100:
                gain_str = f"{self.viewer.brightness_gain:.1f}"
            else:
                gain_str = f"{self.viewer.brightness_gain:.2f}"

            if isinstance(self.viewer.brightness_upper_level, (int, np.integer)):
                upper_str = str(self.viewer.brightness_upper_level)
            else:
                upper_str = f"{self.viewer.brightness_upper_level:.1f}"

            brightness_text = f"Offset: {offset_str}, Gain: {gain_str}, Upper: {upper_str}"
            self.viewer.status_brightness.setText(brightness_text)
        except Exception:
            self.viewer.status_brightness.setText("")
