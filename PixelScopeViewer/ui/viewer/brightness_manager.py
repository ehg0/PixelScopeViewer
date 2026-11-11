"""ImageViewer の brightness・channel 表示設定の管理。"""

from dataclasses import replace

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QMessageBox

from PixelScopeViewer.core.brightness import BrightnessParams, determine_dtype_defaults, merged_dtype_defaults
from PixelScopeViewer.core.constants import GAIN_STEP
from PixelScopeViewer.ui.common.qt_image import numpy_to_qimage
from PixelScopeViewer.ui.common.window import bring_to_front
from PixelScopeViewer.ui.display import BrightnessDialog


class BrightnessManager:
    """brightness parameter、表示設定 dialog、channel の色・表示 ON/OFF を管理する。"""

    def __init__(self, viewer):
        self.viewer = viewer

    def show_brightness_dialog(self):
        """表示設定 dialog を表示する。初回は作成して viewer と signal を接続する。"""
        if self.viewer.state.current_index is None:
            QMessageBox.information(self.viewer, "表示設定", "画像が選択されていません。")
            return

        img = self.viewer.images[self.viewer.state.current_index]
        arr = img.get("base_array", img.get("array"))
        img_path = img.get("path")

        init_offset = self.viewer.state.brightness.offset
        init_gain = self.viewer.state.brightness.gain
        init_upper_level = self._default_upper_level_for_dtype(arr.dtype, self.viewer.state.brightness.upper_level)

        if self.viewer.brightness_dialog is None:
            self.viewer.brightness_dialog = BrightnessDialog(
                self.viewer,
                arr,
                img_path,
                initial_brightness=(init_offset, init_gain, init_upper_level),
                initial_channels=self.viewer.channel_checks,
                initial_colors=self.viewer.channel_colors,
                initial_mode_1ch=self.viewer.channel_display.mode_1ch,
                initial_mode_2ch=self.viewer.channel_display.mode_2ch,
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
            self.viewer.child_dialogs.track(
                self.viewer.brightness_dialog, lambda: setattr(self.viewer, "brightness_dialog", None)
            )
            self.sync_tile_mode()
            params = self.viewer.brightness_dialog.get_brightness()
            self.viewer.state.brightness.offset = params[0]
            self.viewer.state.brightness.gain = params[1]
            self.viewer.state.brightness.upper_level = params[2]
            self.viewer.status_updater.update_brightness_status()
        else:
            # update_for_new_image が brightness_changed を emit し、status bar も更新される
            self.viewer.brightness_dialog.update_for_new_image(
                arr,
                img_path,
                keep_settings=True,
                channel_checks=self.viewer.channel_checks,
                channel_colors=self.viewer.channel_colors,
                initial_mode_1ch=self.viewer.channel_display.mode_1ch,
                initial_mode_2ch=self.viewer.channel_display.mode_2ch,
            )

        # 非表示の場合は保存済みの geometry を復元してから表示する
        if not self.viewer.brightness_dialog.isVisible():
            self.viewer.brightness_dialog.restore_geometry()
        bring_to_front(self.viewer.brightness_dialog)

    def sync_tile_mode(self):
        """表示設定 dialog の brightness の入力範囲と値を、タイル比較モードか 1 枚表示かに合わせる。"""
        dlg = self.viewer.brightness_dialog
        if dlg is None:
            return
        st = self.viewer.state
        if st.tile_mode:
            dlg.brightness_tab.set_tile_mode(
                self.viewer.tiles.registered_dtype_groups(), st.brightness_by_dtype[st.brightness_key(None)]
            )
        else:
            dlg.brightness_tab.set_tile_mode(None)

    def _default_upper_level_for_dtype(self, dtype, current):
        """dtype に合う upper level を返す。

        current が未設定か別 dtype の既定値（float なら 255、整数なら 1.0）の場合、
        float は 1.0、8bit は 255、それ以上は min(最大値, 4095) を返す。それ以外は current を返す。
        """
        if np.issubdtype(dtype, np.floating):
            return 1.0 if current is None or current == 255 else current
        if current is None or current == 1.0:
            # bool など整数以外の dtype は 8bit として扱う
            max_val = np.iinfo(dtype).max if np.issubdtype(dtype, np.integer) else 255
            return 255 if max_val <= 255 else min(max_val, 4095)
        return current

    def reset_brightness_settings(self):
        """brightness を dtype の既定値に戻す。dialog が開いていれば dialog 側で reset する。"""
        handled_by_dialog = False

        if self.viewer.brightness_dialog is not None:
            # dialog から reset の signal を emit させて viewer と同期する
            self.viewer.brightness_dialog.reset_parameters()
            handled_by_dialog = True
        else:
            # 画像がない場合は uint8 の既定値にする。タイル比較モードは最初のタイルの画像の dtype の既定値にする
            base_arr = None
            if self.viewer.state.current_index is not None:
                img = self.viewer.images[self.viewer.state.current_index]
                base_arr = img.get("base_array", img["array"])
            if self.viewer.state.tile_mode:
                d = merged_dtype_defaults(self.viewer.tiles.registered_dtype_groups())
            else:
                d = determine_dtype_defaults(base_arr)
            self.viewer.state.brightness = BrightnessParams(
                d["initial_offset"], d["initial_gain"], d["initial_upper_level"]
            )
            self.viewer.status_updater.update_brightness_status()

        # 画像を切り替えても reset 後の値が保たれるよう保存する
        self._save_current_dtype_params()

        # dialog 経由の場合は dialog 側で再描画される
        if not handled_by_dialog:
            self.viewer.refresh_display()

    def on_brightness_changed(self, offset, gain, upper_level):
        self.viewer.state.brightness.offset = offset
        self.viewer.state.brightness.gain = gain
        self.viewer.state.brightness.upper_level = upper_level

        self._save_current_dtype_params()

        self.viewer.status_updater.update_brightness_status()

        self.viewer.refresh_display(defer_others=True)

    def on_channels_changed(self, channels):
        # 再描画は channel_display の checks_changed を受けた viewer が行う
        self.viewer.channel_display.set_checks(self.viewer._current_n_channels(), channels)

    def on_channel_colors_changed(self, colors):
        # 再描画は channel_display の colors_changed を受けた各画面が行う
        self.viewer.channel_display.set_colors(self.viewer._current_n_channels(), colors)

    def on_mode_1ch_changed(self, mode: str):
        # 再描画は channel_display の modes_changed を受けた viewer が行う
        self.viewer.channel_display.set_mode_1ch(mode)
        self._refresh_thumbnail(lambda arr: arr.ndim == 2 or arr.shape[2] == 1)

    def on_mode_2ch_changed(self, mode: str):
        self.viewer.channel_display.set_mode_2ch(mode)
        self._refresh_thumbnail(lambda arr: arr.ndim == 3 and arr.shape[2] == 2)

    def _refresh_thumbnail(self, applies) -> None:
        """表示中の画像が applies(arr) を満たす場合、表示モードに合わせて navigator の thumbnail を作り直す。"""
        if self.viewer.state.current_index is None:
            return
        img = self.viewer.images[self.viewer.state.current_index]
        base_arr = img.get("base_array", img.get("array"))
        if not applies(base_arr):
            return
        thumb = numpy_to_qimage(self.viewer.renderer.thumbnail_array(base_arr))
        img["thumbnail_pixmap"] = QPixmap.fromImage(thumb).scaled(250, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.viewer.navigator_widget.update_thumbnail()

    def _save_current_dtype_params(self) -> None:
        # タイル比較モードは active タイルが空欄でも共通の key に保存する
        st = self.viewer.state
        arr = None
        if st.current_index is not None:
            img = self.viewer.images[st.current_index]
            arr = img.get("base_array", img["array"])
        key = st.brightness_key(arr)
        if key is not None:
            st.brightness_by_dtype[key] = replace(st.brightness)

    def adjust_gain_step(self, amount):
        """gain を 2 倍（amount > 0）または 1/2 倍（amount < 0）にする。"""
        if self.viewer.state.current_index is None:
            return

        current_gain = self.viewer.state.brightness.gain

        new_gain = current_gain / GAIN_STEP if amount < 0 else current_gain * GAIN_STEP

        self.viewer.state.brightness.gain = new_gain

        self._save_current_dtype_params()

        if self.viewer.brightness_dialog is not None:
            self.viewer.brightness_dialog.set_gain(new_gain)

        self.viewer.status_updater.update_brightness_status()

        self.viewer.refresh_display()
