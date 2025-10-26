"""Brightness and channel adjustment management for ImageViewer.

This module handles brightness parameter management and display dialog coordination.
"""

import numpy as np
from PySide6.QtWidgets import QMessageBox
from ..dialogs import BrightnessDialog
from ..dialogs.display.core import apply_brightness_adjustment as apply_brightness_core


class BrightnessManager:
    """Manages brightness and channel adjustment operations.

    This class coordinates brightness parameters, display dialog, and
    channel selection/color management.
    """

    def __init__(self, viewer):
        """Initialize brightness manager.

        Args:
            viewer: ImageViewer instance
        """
        self.viewer = viewer

    def show_brightness_dialog(self):
        """表示設定ダイアログを表示します。

        現在選択中の画像が存在しない場合は情報ダイアログを表示して終了します。

        このメソッドはダイアログを初めて作成する際にダイアログを生成し、
        ダイアログからのシグナルを購読してビューア側の輝度パラメータを同期します。

        例外やエラーは GUI 内でユーザ向けに通知されます。
        """
        if self.viewer.current_index is None:
            QMessageBox.information(self.viewer, "表示設定", "画像が選択されていません。")
            return

        img = self.viewer.images[self.viewer.current_index]
        arr = img.get("base_array", img.get("array"))
        img_path = img.get("path")

        # Create dialog if it doesn't exist
        # For float images, prefer saturation initial value of 1 unless user already changed it
        try:
            is_float_img = np.issubdtype(arr.dtype, np.floating)
        except Exception:
            is_float_img = False

        init_offset = self.viewer.brightness_offset
        init_gain = self.viewer.brightness_gain
        init_sat = self._default_saturation_for_dtype(arr.dtype, self.viewer.brightness_saturation)

        if self.viewer.brightness_dialog is None:
            self.viewer.brightness_dialog = BrightnessDialog(
                self.viewer,
                arr,
                img_path,
                initial_brightness=(init_offset, init_gain, init_sat),
                initial_channels=self.viewer.channel_checks,
                initial_colors=self.viewer.channel_colors,
            )
            self.viewer.brightness_dialog.brightness_changed.connect(
                self.viewer.brightness_manager.on_brightness_changed
            )
            self.viewer.brightness_dialog.channels_changed.connect(self.viewer.brightness_manager.on_channels_changed)
            self.viewer.brightness_dialog.channel_colors_changed.connect(
                self.viewer.brightness_manager.on_channel_colors_changed
            )
            # Initialize status bar with current parameters
            params = self.viewer.brightness_dialog.get_brightness()
            self.viewer.brightness_offset = params[0]
            self.viewer.brightness_gain = params[1]
            self.viewer.brightness_saturation = params[2]
            self.viewer.update_brightness_status()
        else:
            # Update dialog for new image
            self.viewer.brightness_dialog.update_for_new_image(arr, img_path, channel_checks=self.viewer.channel_checks)
            # Note: update_for_new_image will emit brightness_changed signal
            # which will update the status bar through on_brightness_changed

        # 表示中のダイアログは show() を再実行しない(位置が変わるのを防ぐ)
        if self.viewer.brightness_dialog.isVisible():
            try:
                self.viewer.brightness_dialog.raise_()
                self.viewer.brightness_dialog.activateWindow()
            except Exception:
                pass
            return

        # 非表示(前回閉じた等)の場合のみ再表示し、可能なら保存ジオメトリを復元
        try:
            from ..dialogs.display import BrightnessDialog as _BD

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

    def _default_saturation_for_dtype(self, dtype, current):
        """Return a dtype-appropriate saturation value given current value.

        Rules:
        - Float: prefer 1.0 if current is None or an integer default (255)
        - Integer: prefer 255 for 8-bit, or min(max_val, 4095) for higher bit depth
                   if current is None or a float default (1.0)
        Otherwise, keep current.
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
        """輝度設定を初期値に戻します(Ctrl+R 等から呼び出されます)。

        動作:
        - 輝度ダイアログが開いている場合はダイアログ側のリセット処理に委譲し、
          ダイアログが閉じている場合はビューア側でパラメータを手動でリセットします。
        """
        handled_by_dialog = False

        if self.viewer.brightness_dialog is not None:
            # Let the dialog emit the reset signal so the viewer stays in sync
            self.viewer.brightness_dialog.reset_parameters()
            handled_by_dialog = True
        else:
            # Reset brightness parameters manually when dialog is closed
            self.viewer.brightness_offset = 0
            self.viewer.brightness_gain = 1.0
            # Default saturation depends on image dtype: 1.0 for float, 255 for integer
            if self.viewer.current_index is not None:
                try:
                    img = self.viewer.images[self.viewer.current_index]
                    base_arr = img.get("base_array", img.get("array"))
                    if np.issubdtype(base_arr.dtype, np.floating):
                        self.viewer.brightness_saturation = 1.0
                    else:
                        self.viewer.brightness_saturation = 255
                except Exception:
                    self.viewer.brightness_saturation = 255
            else:
                self.viewer.brightness_saturation = 255
            self.viewer.update_brightness_status()

        # Refresh display if the dialog didn't already trigger it
        if not handled_by_dialog and self.viewer.current_index is not None:
            self.viewer.display_image(self.viewer.images[self.viewer.current_index]["array"])

    def on_brightness_changed(self, offset, gain, saturation):
        """Handle brightness parameter changes.

        Args:
            offset: Offset value
            gain: Gain value
            saturation: Saturation level
        """
        self.viewer.brightness_offset = offset
        self.viewer.brightness_gain = gain
        self.viewer.brightness_saturation = saturation

        # Update status bar
        self.viewer.update_brightness_status()

        # Refresh display with new brightness settings
        if self.viewer.current_index is not None:
            self.viewer.display_image(self.viewer.images[self.viewer.current_index]["array"])

    def on_channels_changed(self, channels):
        """Handle channel selection changes.

        Args:
            channels: List of bools for channel visibility
        """
        self.viewer.channel_checks = channels

        # Refresh display with new channel selection
        if self.viewer.current_index is not None:
            self.viewer.display_image(self.viewer.images[self.viewer.current_index]["array"])

    def on_channel_colors_changed(self, colors):
        """Handle channel color changes.

        Args:
            colors: List of QColor objects for channel colors
        """
        self.viewer.channel_colors = colors

        # Refresh display with new channel colors
        if self.viewer.current_index is not None:
            self.viewer.display_image(self.viewer.images[self.viewer.current_index]["array"])

    def apply_brightness_adjustment(self, arr: np.ndarray) -> np.ndarray:
        """画像配列に対して輝度補正を適用して新しい配列を返します。

        使用する式:
            yout = gain * (yin - offset) / saturation * 255

        パラメータ:
            arr: 入力画像の NumPy 配列(任意の dtype を受け付けます)

        戻り値:
            uint8 にクリップ/変換された補正後の配列を返します。

        注意:
            saturation が 0 の場合はゼロ除算を避けるため元配列をそのまま返します。
        """
        return apply_brightness_core(
            arr, self.viewer.brightness_offset, self.viewer.brightness_gain, self.viewer.brightness_saturation
        )

    def adjust_gain_step(self, amount):
        """輝度ゲイン調整を行います。

        説明:
            - amount が負の場合はゲインを半分(暗くする)
            - amount が正の場合はゲインを2倍(明るくする)
            - 表示設定ダイアログのゲイン調整と同じ挙動です。

        パラメータ:
            amount: 調整方向(-1 で×0.5、+1 で×2.0)
        """
        if self.viewer.current_index is None:
            return

        # Update gain: amount < 0 -> darker (gain *= 0.5), amount > 0 -> brighter (gain *= 2)
        current_gain = self.viewer.brightness_gain

        if amount < 0:
            new_gain = current_gain * 0.5
        else:
            new_gain = current_gain * 2.0

        # Update brightness_gain property
        self.viewer.brightness_gain = new_gain

        # Update dialog if it exists
        if self.viewer.brightness_dialog is not None:
            self.viewer.brightness_dialog.set_gain(new_gain)

        # Update status bar
        self.viewer.update_brightness_status()

        # Refresh display with new gain
        img = self.viewer.images[self.viewer.current_index]
        self.viewer.display_image(img["array"])
