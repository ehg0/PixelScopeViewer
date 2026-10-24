"""ImageViewer の brightness・channel 表示設定の管理。"""

import contextlib

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QMessageBox

from PixelScopeViewer.core.constants import DTYPE_DEFAULTS, GAIN_STEP, get_dtype_defaults
from PixelScopeViewer.core.image_io import numpy_to_qimage
from PixelScopeViewer.ui.dialogs import BrightnessDialog
from PixelScopeViewer.ui.dialogs.display import BrightnessDialog as _BD
from PixelScopeViewer.ui.dialogs.display.core import apply_brightness_adjustment as apply_brightness_core
from PixelScopeViewer.ui.dialogs.display.tabs.logic.brightness_utils import determine_dtype_defaults
from PixelScopeViewer.ui.utils import MODE_1CH_GRAYSCALE, MODE_1CH_JET, MODE_2CH_COMPOSITE, MODE_2CH_FLOW_HSV


class BrightnessManager:
    """brightness parameter、表示設定 dialog、channel の色・表示 ON/OFF を管理する。"""

    def __init__(self, viewer):
        self.viewer = viewer
        # 画像を切り替えても dtype（float/uint8/uint16）ごとに直前の設定を保つ
        self._params_by_dtype = {}
        for dtype_key in DTYPE_DEFAULTS:
            defaults = get_dtype_defaults(dtype_key)
            self._params_by_dtype[dtype_key] = (
                defaults.get("initial_offset"),
                defaults.get("initial_gain"),
                defaults.get("initial_upper_level"),
            )

    def show_brightness_dialog(self):
        """表示設定 dialog を表示する。初回は作成して viewer と signal を接続する。"""
        if self.viewer.current_index is None:
            QMessageBox.information(self.viewer, "表示設定", "画像が選択されていません。")
            return

        img = self.viewer.images[self.viewer.current_index]
        arr = img.get("base_array", img.get("array"))
        img_path = img.get("path")

        init_offset = self.viewer.brightness_offset
        init_gain = self.viewer.brightness_gain
        init_upper_level = self._default_upper_level_for_dtype(arr.dtype, self.viewer.brightness_upper_level)

        if self.viewer.brightness_dialog is None:
            self.viewer.brightness_dialog = BrightnessDialog(
                self.viewer,
                arr,
                img_path,
                initial_brightness=(init_offset, init_gain, init_upper_level),
                initial_channels=self.viewer.channel_checks,
                initial_colors=self.viewer.channel_colors,
                initial_mode_1ch=self.viewer.color_manager.mode_1ch,
                initial_mode_2ch=self.viewer.color_manager.mode_2ch,
            )
            self.viewer.brightness_dialog.brightness_changed.connect(
                self.viewer.brightness_manager.on_brightness_changed
            )
            self.viewer.brightness_dialog.channels_changed.connect(self.viewer.brightness_manager.on_channels_changed)
            self.viewer.brightness_dialog.channel_colors_changed.connect(
                self.viewer.brightness_manager.on_channel_colors_changed
            )
            self.viewer.brightness_dialog.mode_1ch_changed.connect(self.viewer.brightness_manager.on_mode_1ch_changed)
            self.viewer.brightness_dialog.mode_2ch_changed.connect(self.viewer.brightness_manager.on_mode_2ch_changed)
            # window 状態の同期対象に加える
            self.viewer._child_dialogs.append(self.viewer.brightness_dialog)

            def on_closed():
                if self.viewer.brightness_dialog in self.viewer._child_dialogs:
                    self.viewer._child_dialogs.remove(self.viewer.brightness_dialog)
                self.viewer.brightness_dialog = None

            self.viewer.brightness_dialog.finished.connect(on_closed)
            params = self.viewer.brightness_dialog.get_brightness()
            self.viewer.brightness_offset = params[0]
            self.viewer.brightness_gain = params[1]
            self.viewer.brightness_upper_level = params[2]
            self.viewer.update_brightness_status()
        else:
            # update_for_new_image が brightness_changed を emit し、status bar も更新される
            self.viewer.brightness_dialog.update_for_new_image(
                arr,
                img_path,
                keep_settings=True,
                channel_checks=self.viewer.channel_checks,
                channel_colors=self.viewer.channel_colors,
                initial_mode_1ch=self.viewer.color_manager.mode_1ch,
                initial_mode_2ch=self.viewer.color_manager.mode_2ch,
            )

        # 表示中の dialog に show() を再実行すると位置が変わるため前面に出すだけにする
        if self.viewer.brightness_dialog.isVisible():
            try:
                if self.viewer.brightness_dialog.isMinimized():
                    self.viewer.brightness_dialog.showNormal()
                self.viewer.brightness_dialog.raise_()
                self.viewer.brightness_dialog.activateWindow()
            except Exception:
                pass
            return

        # 非表示の場合は保存済みの geometry を復元して表示する
        try:
            if getattr(_BD, "_saved_geometry", None):
                self.viewer.brightness_dialog.restoreGeometry(_BD._saved_geometry)
        except Exception:
            pass
        self.viewer.brightness_dialog.show()
        try:
            self.viewer.brightness_dialog.raise_()
            self.viewer.brightness_dialog.activateWindow()
        except Exception:
            pass

    def _default_upper_level_for_dtype(self, dtype, current):
        """dtype に合う upper level を返す。

        current が未設定か別 dtype の既定値（float なら 255、整数なら 1.0）の場合、
        float は 1.0、8bit は 255、それ以上は min(最大値, 4095) を返す。それ以外は current を返す。
        """
        try:
            if np.issubdtype(dtype, np.floating):
                return 1.0 if (current is None or current == 255) else current
            else:
                if current is None or current == 1.0:
                    try:
                        max_val = np.iinfo(dtype).max
                    except Exception:
                        max_val = 255
                    return 255 if max_val <= 255 else min(max_val, 4095)
                return current
        except Exception:
            return current if current is not None else 255

    def reset_brightness_settings(self):
        """brightness を dtype の既定値に戻す。dialog が開いていれば dialog 側で reset する。"""
        handled_by_dialog = False

        if self.viewer.brightness_dialog is not None:
            # dialog から reset の signal を emit させて viewer と同期する
            self.viewer.brightness_dialog.reset_parameters()
            handled_by_dialog = True
        else:
            self.viewer.brightness_offset = 0
            self.viewer.brightness_gain = 1.0
            self.viewer.brightness_upper_level = 255
            if self.viewer.current_index is not None:
                try:
                    img = self.viewer.images[self.viewer.current_index]
                    base_arr = img.get("base_array", img.get("array"))
                    dtype_defaults = determine_dtype_defaults(base_arr)
                    self.viewer.brightness_offset = dtype_defaults.get("initial_offset", 0)
                    self.viewer.brightness_gain = dtype_defaults.get("initial_gain", 1.0)
                    self.viewer.brightness_upper_level = dtype_defaults.get("initial_upper_level", 255)
                except Exception:
                    pass
            self.viewer.update_brightness_status()

        # 画像を切り替えても reset 後の値が保たれるよう保存する
        self._save_current_dtype_params()

        # dialog 経由の場合は dialog 側で再描画される
        if not handled_by_dialog and self.viewer.current_index is not None:
            self.viewer.display_image(self.viewer.images[self.viewer.current_index]["array"])

    def on_brightness_changed(self, offset, gain, upper_level):
        self.viewer.brightness_offset = offset
        self.viewer.brightness_gain = gain
        self.viewer.brightness_upper_level = upper_level

        self._save_current_dtype_params()

        self.viewer.update_brightness_status()

        self.viewer._cached_display_array = None
        self.viewer._cached_display_params = None

        if self.viewer.current_index is not None:
            self.viewer.display_image(self.viewer.images[self.viewer.current_index]["array"])

    def on_channels_changed(self, channels):
        self.viewer.channel_checks = channels
        # 現在の channel 数の設定として保存する
        try:
            img = self.viewer.images[self.viewer.current_index]
            arr = img.get("base_array", img.get("array"))
            n = arr.shape[2] if getattr(arr, "ndim", 0) >= 3 else 1
            self.viewer.color_manager.set_checks(n, channels)
        except Exception:
            pass

        self.viewer._cached_display_array = None
        self.viewer._cached_display_params = None

        if self.viewer.current_index is not None:
            self.viewer.display_image(self.viewer.images[self.viewer.current_index]["array"])

    def on_channel_colors_changed(self, colors):
        self.viewer.channel_colors = colors
        # 現在の channel 数の設定として保存する
        try:
            img = self.viewer.images[self.viewer.current_index]
            arr = img.get("base_array", img.get("array"))
            n = arr.shape[2] if getattr(arr, "ndim", 0) >= 3 else 1
            self.viewer.color_manager.set_colors(n, colors)
        except Exception:
            pass

        self.viewer._cached_display_array = None
        self.viewer._cached_display_params = None

        if self.viewer.current_index is not None:
            self.viewer.display_image(self.viewer.images[self.viewer.current_index]["array"])

        if self.viewer._analysis_dialog is not None:
            with contextlib.suppress(Exception):
                self.viewer._analysis_dialog.update_contents()

    def on_mode_1ch_changed(self, mode: str):
        if mode not in (MODE_1CH_GRAYSCALE, MODE_1CH_JET):
            return
        self.viewer.color_manager.set_mode_1ch(mode)

        self.viewer._cached_display_array = None
        self.viewer._cached_display_params = None

        if self.viewer.current_index is not None:
            # 1ch 画像の thumbnail を新しいモードで作り直す
            img = self.viewer.images[self.viewer.current_index]
            base_arr = img.get("base_array", img.get("array"))
            if (base_arr.ndim == 2) or (base_arr.ndim == 3 and base_arr.shape[2] == 1):
                try:
                    thumb_arr = self.viewer._prepare_thumbnail_array(base_arr)
                    thumb_qimg = numpy_to_qimage(thumb_arr)
                    thumb_pixmap = QPixmap.fromImage(thumb_qimg).scaled(
                        250, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    img["thumbnail_pixmap"] = thumb_pixmap
                    if hasattr(self.viewer, "navigator_widget"):
                        self.viewer.navigator_widget.update_thumbnail()
                except Exception:
                    pass
            self.viewer.display_image(img["array"])

    def on_mode_2ch_changed(self, mode: str):

        if mode not in (MODE_2CH_COMPOSITE, MODE_2CH_FLOW_HSV):
            return
        self.viewer.color_manager.set_mode_2ch(mode)

        self.viewer._cached_display_array = None
        self.viewer._cached_display_params = None

        if self.viewer.current_index is not None:
            # 2ch 画像の thumbnail を新しいモードで作り直す
            img = self.viewer.images[self.viewer.current_index]
            base_arr = img.get("base_array", img.get("array"))
            if base_arr.ndim == 3 and base_arr.shape[2] == 2:
                try:
                    thumb_arr = self.viewer._prepare_thumbnail_array(base_arr)
                    thumb_qimg = numpy_to_qimage(thumb_arr)
                    thumb_pixmap = QPixmap.fromImage(thumb_qimg).scaled(
                        250, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    img["thumbnail_pixmap"] = thumb_pixmap

                    if hasattr(self.viewer, "navigator_widget"):
                        self.viewer.navigator_widget.update_thumbnail()
                except Exception:
                    pass

            self.viewer.display_image(img["array"])

    def apply_brightness_adjustment(self, arr: np.ndarray) -> np.ndarray:
        """dtype ごとに保存した brightness を適用し、uint8 の配列を返す。

        変換式: gain * (x - offset) / (upper_level - offset) * 255
        """
        dtype_key = self.viewer.brightness_manager._dtype_key(arr.dtype)
        stored_params = self.viewer.brightness_manager._params_by_dtype.get(dtype_key)
        self.viewer.brightness_offset, self.viewer.brightness_gain, self.viewer.brightness_upper_level = stored_params
        return apply_brightness_core(
            arr, self.viewer.brightness_offset, self.viewer.brightness_gain, self.viewer.brightness_upper_level
        )

    # ------------------------ dtype ごとの設定の保存 ------------------------
    def _dtype_key(self, dtype) -> str:
        """numpy の dtype を保存用の key（float/uint8/uint16）に変換する。"""
        try:
            if np.issubdtype(dtype, np.floating):
                return "float"
            if np.issubdtype(dtype, np.integer):
                try:
                    max_val = np.iinfo(dtype).max
                except Exception:
                    max_val = 255
                return "uint16" if max_val > 255 else "uint8"
        except Exception:
            pass
        return "uint8"

    def _save_current_dtype_params(self) -> None:
        if self.viewer.current_index is None:
            return
        try:
            img = self.viewer.images[self.viewer.current_index]
            arr = img.get("base_array", img.get("array"))
            key = self._dtype_key(arr.dtype)
            self._params_by_dtype[key] = (
                self.viewer.brightness_offset,
                self.viewer.brightness_gain,
                self.viewer.brightness_upper_level,
            )
        except Exception:
            pass

    def adjust_gain_step(self, amount):
        """gain を 2 倍（amount > 0）または 1/2 倍（amount < 0）にする。"""
        if self.viewer.current_index is None:
            return

        current_gain = self.viewer.brightness_gain

        new_gain = current_gain / GAIN_STEP if amount < 0 else current_gain * GAIN_STEP

        self.viewer.brightness_gain = new_gain

        self._save_current_dtype_params()

        if self.viewer.brightness_dialog is not None:
            self.viewer.brightness_dialog.set_gain(new_gain)

        self.viewer.update_brightness_status()

        img = self.viewer.images[self.viewer.current_index]
        self.viewer.display_image(img["array"])
