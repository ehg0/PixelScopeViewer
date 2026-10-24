"""brightness 調整 tab。"""

import math

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from PixelScopeViewer.core.brightness import BrightnessParams, determine_dtype_defaults
from PixelScopeViewer.core.constants import get_dtype_defaults
from PixelScopeViewer.ui.display.tabs.logic import clamp_value, round_to_power_of_2
from PixelScopeViewer.ui.display.tabs.logic.brightness_builder import BrightnessUIBuilder


class BrightnessTab(QWidget):
    """offset・gain・upper level を slider と spin box で調整する tab。"""

    brightness_changed = Signal(float, float, float)  # offset, gain, upper_level

    def __init__(self, parent=None, image_array=None, image_path=None):
        super().__init__(parent)
        self.viewer = parent.viewer

        self.image_array = image_array
        self.image_path = image_path

        self.roi = self._get_roi()
        # 親で ROI が変わったら auto scale 用の ROI を更新する
        if self.viewer and hasattr(self.viewer, "roi_changed"):
            self.viewer.roi_changed.connect(self._on_roi_changed)

        # dtype ごとの (offset, gain, upper_level)
        self.dtype_params = {}

        # 画像の dtype から初期値を決める
        defaults = determine_dtype_defaults(image_array)
        self.current_dtype = defaults["dtype_key"]
        self.is_float_type = defaults["is_float_type"]
        self.initial_offset = defaults["initial_offset"]
        self.initial_gain = defaults["initial_gain"]
        self.initial_upper_level = defaults["initial_upper_level"]
        self.offset_range = defaults["offset_range"]
        self.upper_level_range = defaults["upper_level_range"]

        # gain の範囲
        self._gain_log2_min = -7  # 2^-7 = 1/128
        self._gain_log2_max = 10  # 2^10 = 1024
        self._gain_spinbox_min = 2**-7
        self._gain_spinbox_max = 1024.0

        self._build_ui()

        self._reset_to_initial()

    # ------------------------ UI 構築 ------------------------
    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(25, 25, 25, 25)

        builder = BrightnessUIBuilder(self)

        self.dtype_combo = builder.build_dtype_selector(main_layout, self.current_dtype, self._on_dtype_changed)

        self.auto_scale_cb, self.use_roi_cb, self.set_as_default = builder.build_autoscale(
            main_layout, self._on_autoscale_changed, self._save_current_params
        )

        self.offset_slider, self.offset_spinbox = builder.build_offset_controls(
            main_layout,
            self.initial_offset,
            self.offset_range,
            self.is_float_type,
            self._on_offset_slider_changed,
            self._on_offset_spinbox_changed,
        )

        self.gain_slider, self.gain_spinbox = builder.build_gain_controls(
            main_layout,
            self.initial_gain,
            self._gain_log2_min,
            self._gain_log2_max,
            self._gain_spinbox_min,
            self._gain_spinbox_max,
            self._on_gain_slider_changed,
            self._on_gain_spinbox_changed,
        )

        self.upper_level_slider, self.upper_level_spinbox = builder.build_upper_level_controls(
            main_layout,
            self.initial_upper_level,
            self.upper_level_range,
            self.is_float_type,
            self._on_upper_level_slider_changed,
            self._on_upper_level_spinbox_changed,
        )

        self.reset_button = builder.build_formula_and_reset(main_layout, self._on_reset_clicked)

    # ------------------------ slot ------------------------
    def _on_offset_slider_changed(self, value):
        self.offset_spinbox.blockSignals(True)
        self.offset_spinbox.setValue(value)
        self.offset_spinbox.blockSignals(False)
        self._save_current_params()
        self._emit_brightness_changed()

    def _on_offset_spinbox_changed(self, value):
        self.offset_slider.blockSignals(True)
        self.offset_slider.setValue(int(value))
        self.offset_slider.blockSignals(False)
        self._save_current_params()
        self._emit_brightness_changed()

    def _on_gain_slider_changed(self, value):
        # slider の値は log2(gain)
        actual_value = 2**value
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(actual_value)
        self.gain_spinbox.blockSignals(False)
        self._save_current_params()
        self._emit_brightness_changed()

    def _on_gain_spinbox_changed(self, value):
        # 最も近い 2 の累乗に丸める
        if value > 0:
            rounded = round_to_power_of_2(value, self._gain_log2_min, self._gain_log2_max)
            log2_value = round(math.log2(rounded))

            self.gain_spinbox.blockSignals(True)
            self.gain_spinbox.setValue(rounded)
            self.gain_spinbox.blockSignals(False)

            self.gain_slider.blockSignals(True)
            self.gain_slider.setValue(log2_value)
            self.gain_slider.blockSignals(False)

            self._save_current_params()
            self._emit_brightness_changed()
        else:
            self._reset_gain_to_default()

    def _on_upper_level_slider_changed(self, value):
        self.upper_level_spinbox.blockSignals(True)
        self.upper_level_spinbox.setValue(value)
        self.upper_level_spinbox.blockSignals(False)
        self._save_current_params()
        self._emit_brightness_changed()

    def _on_upper_level_spinbox_changed(self, value):
        self.upper_level_slider.blockSignals(True)
        self.upper_level_slider.setValue(int(value))
        self.upper_level_slider.blockSignals(False)
        self._save_current_params()
        self._emit_brightness_changed()

    def _on_reset_clicked(self):
        self.reset_parameters()

    def _on_dtype_changed(self, dtype_text):
        """combo box で選択した dtype に入力範囲を切り替える。"""
        prev_params = (
            self.offset_spinbox.value(),
            self.gain_spinbox.value(),
            self.upper_level_spinbox.value(),
        )
        self._save_current_params()

        self.current_dtype = dtype_text
        self._update_ranges_for_dtype(dtype_text)
        self._configure_offset_widgets()
        self._configure_gain_widgets()
        self._configure_upper_level_widgets()

        # 新しい dtype の保存済み設定がなければ、直前の値を引き継ぐ
        if dtype_text in self.dtype_params:
            offset, gain, upper_level = self.dtype_params[dtype_text]
        else:
            offset, gain, upper_level = prev_params

        clamped_offset, clamped_gain, clamped_upper_level = self._apply_values(offset, gain, upper_level, clamp=True)
        self.dtype_params[self.current_dtype] = (clamped_offset, clamped_gain, clamped_upper_level)
        self._emit_brightness_changed()

    def _on_autoscale_changed(self):
        if self.auto_scale_cb.isChecked():
            self._apply_autoscale()
        else:
            new_offset, new_gain, new_upper_level = self.dtype_params[self.current_dtype]
            self._apply_values(new_offset, new_gain, new_upper_level, clamp=True)
            self._emit_brightness_changed()

    # ------------------------ 入力範囲の設定 ------------------------
    def _update_ranges_for_dtype(self, dtype_key):
        defaults = get_dtype_defaults(dtype_key)
        self.is_float_type = defaults["is_float_type"]
        self.offset_range = defaults["offset_range"]
        self.upper_level_range = defaults["upper_level_range"]

    def _configure_offset_widgets(self):
        self.offset_slider.blockSignals(True)
        self.offset_slider.setRange(int(self.offset_range[0]), int(self.offset_range[1]))
        self.offset_slider.blockSignals(False)
        self.offset_spinbox.blockSignals(True)
        self.offset_spinbox.setRange(self.offset_range[0], self.offset_range[1])
        if self.is_float_type:
            self.offset_spinbox.setDecimals(3)
            self.offset_spinbox.setSingleStep(0.01)
        else:
            self.offset_spinbox.setDecimals(0)
            self.offset_spinbox.setSingleStep(1)
        self.offset_spinbox.blockSignals(False)

    def _configure_upper_level_widgets(self):
        self.upper_level_slider.blockSignals(True)
        if self.is_float_type:
            self.upper_level_slider.setRange(int(self.upper_level_range[0]), int(self.upper_level_range[1]))
        else:
            self.upper_level_slider.setRange(self.upper_level_range[0], self.upper_level_range[1])
        self.upper_level_slider.blockSignals(False)
        self.upper_level_spinbox.blockSignals(True)
        self.upper_level_spinbox.setRange(self.upper_level_range[0], self.upper_level_range[1])
        if self.is_float_type:
            self.upper_level_spinbox.setDecimals(3)
            self.upper_level_spinbox.setSingleStep(0.01)
        else:
            self.upper_level_spinbox.setDecimals(0)
            self.upper_level_spinbox.setSingleStep(1)
        self.upper_level_spinbox.blockSignals(False)

    def _configure_gain_widgets(self):
        self.gain_slider.blockSignals(True)
        self.gain_slider.setRange(self._gain_log2_min, self._gain_log2_max)
        self.gain_slider.blockSignals(False)

        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setRange(self._gain_spinbox_min, self._gain_spinbox_max)
        self.gain_spinbox.blockSignals(False)

    def _apply_values(self, offset, gain, upper_level, clamp=True):
        """値を widget に設定する。gain は 2 の累乗に丸め、clamp が True なら入力範囲に収める。

        Returns:
            実際に設定した (offset, gain, upper_level)。
        """
        if clamp:
            offset = clamp_value(offset, self.offset_range[0], self.offset_range[1])
            gain = clamp_value(gain, self._gain_spinbox_min, self._gain_spinbox_max)
            gain = round_to_power_of_2(gain, self._gain_log2_min, self._gain_log2_max)
            upper_level = clamp_value(upper_level, self.upper_level_range[0], self.upper_level_range[1])
        else:
            gain = round_to_power_of_2(gain, self._gain_log2_min, self._gain_log2_max)

        gain_log2 = round(math.log2(gain))

        self.offset_slider.blockSignals(True)
        self.offset_spinbox.blockSignals(True)
        self.offset_spinbox.setValue(offset)
        self.offset_slider.setValue(int(offset))
        self.offset_slider.blockSignals(False)
        self.offset_spinbox.blockSignals(False)

        self.gain_slider.blockSignals(True)
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(gain)
        self.gain_slider.setValue(gain_log2)
        self.gain_slider.blockSignals(False)
        self.gain_spinbox.blockSignals(False)

        self.upper_level_slider.blockSignals(True)
        self.upper_level_spinbox.blockSignals(True)
        self.upper_level_spinbox.setValue(upper_level)
        self.upper_level_slider.setValue(int(upper_level))
        self.upper_level_slider.blockSignals(False)
        self.upper_level_spinbox.blockSignals(False)

        return offset, gain, upper_level

    # ------------------------ 状態の保存 ------------------------
    def _save_current_params(self):
        current_params = (
            self.offset_spinbox.value(),
            self.gain_spinbox.value(),
            self.upper_level_spinbox.value(),
        )
        self.dtype_params[self.current_dtype] = current_params

    def _sync_to_manager(self):
        """現在の dtype の設定を viewer の brightness_manager に反映する。"""
        try:
            dialog = self.parent()
            if dialog and hasattr(dialog, "parent") and callable(dialog.parent):
                viewer = dialog.parent()
                if viewer and hasattr(viewer, "state"):
                    offset, gain, upper_level = self.dtype_params.get(self.current_dtype, (0, 1.0, 255))
                    viewer.state.brightness_by_dtype[self.current_dtype] = BrightnessParams(offset, gain, upper_level)
        except Exception:
            pass

    def _reset_gain_to_default(self):
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(1.0)
        self.gain_spinbox.blockSignals(False)

        self.gain_slider.blockSignals(True)
        self.gain_slider.setValue(0)
        self.gain_slider.blockSignals(False)

        self._save_current_params()
        self._emit_brightness_changed()

    # ------------------------ 公開 API ------------------------
    def _emit_brightness_changed(self):
        offset = self.offset_spinbox.value()
        gain = self.gain_spinbox.value()
        upper_level = self.upper_level_spinbox.value()
        self.brightness_changed.emit(offset, gain, upper_level)
        self._sync_to_manager()

    def set_gain(self, gain_value):
        """gain を 2 の累乗に丸めて設定する。"""
        rounded = round_to_power_of_2(gain_value, self._gain_log2_min, self._gain_log2_max)
        log2_value = round(math.log2(rounded))

        self.gain_slider.blockSignals(True)
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(rounded)
        self.gain_slider.setValue(log2_value)
        self.gain_slider.blockSignals(False)
        self.gain_spinbox.blockSignals(False)
        self._save_current_params()
        self._emit_brightness_changed()

    def reset_parameters(self):
        """全 parameter を初期値に戻す。"""
        self._reset_to_initial()
        self._save_current_params()
        self._emit_brightness_changed()

    def _reset_to_initial(self):
        rounded_gain = round_to_power_of_2(self.initial_gain, self._gain_log2_min, self._gain_log2_max)
        gain_log2 = round(math.log2(rounded_gain))

        self.offset_slider.blockSignals(True)
        self.offset_spinbox.blockSignals(True)
        self.offset_spinbox.setValue(self.initial_offset)
        self.offset_slider.setValue(int(self.initial_offset))
        self.offset_slider.blockSignals(False)
        self.offset_spinbox.blockSignals(False)

        self.gain_slider.blockSignals(True)
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(rounded_gain)
        self.gain_slider.setValue(gain_log2)
        self.gain_slider.blockSignals(False)
        self.gain_spinbox.blockSignals(False)

        self.upper_level_slider.blockSignals(True)
        self.upper_level_spinbox.blockSignals(True)
        self.upper_level_spinbox.setValue(self.initial_upper_level)
        self.upper_level_slider.setValue(int(self.initial_upper_level))
        self.upper_level_slider.blockSignals(False)
        self.upper_level_spinbox.blockSignals(False)

        self.dtype_params[self.current_dtype] = (self.initial_offset, rounded_gain, self.initial_upper_level)

    def get_parameters(self):
        """(offset, gain, upper_level) を返す。"""
        return (
            self.offset_spinbox.value(),
            self.gain_spinbox.value(),
            self.upper_level_spinbox.value(),
        )

    def update_for_new_image(self, image_array=None, image_path=None, keep_settings=True):
        """新しい画像の dtype に合わせて入力範囲と値を更新する。

        Args:
            image_array: 画像配列。
            image_path: 画像ファイルのパス。
            keep_settings: dtype ごとに保存した設定を使うか。False の場合は初期値に戻す。
        """
        old_dtype = self.current_dtype
        old_params = (
            self.offset_spinbox.value(),
            self.gain_spinbox.value(),
            self.upper_level_spinbox.value(),
        )

        self.image_array = image_array
        self.image_path = image_path

        # auto scale の場合は画像の値の範囲に合わせるだけ
        if self.auto_scale_cb.isChecked():
            self._apply_autoscale()
            return

        defaults = determine_dtype_defaults(image_array, image_path)
        self.current_dtype = defaults["dtype_key"]
        self.is_float_type = defaults["is_float_type"]
        self.initial_offset = defaults["initial_offset"]
        self.initial_gain = defaults["initial_gain"]
        self.initial_upper_level = defaults["initial_upper_level"]
        self.offset_range = defaults["offset_range"]
        self.upper_level_range = defaults["upper_level_range"]

        if keep_settings:
            self.dtype_params[old_dtype] = old_params

        if hasattr(self, "dtype_combo"):
            self.dtype_combo.blockSignals(True)
            self.dtype_combo.setCurrentText(self.current_dtype)
            self.dtype_combo.blockSignals(False)

        if keep_settings and self.current_dtype in self.dtype_params:
            new_offset, new_gain, new_upper_level = self.dtype_params[self.current_dtype]
        else:
            new_offset = self.initial_offset
            new_gain = self.initial_gain
            new_upper_level = self.initial_upper_level

        self._configure_offset_widgets()
        self._configure_gain_widgets()
        self._configure_upper_level_widgets()

        clamped_offset, clamped_gain, clamped_upper_level = self._apply_values(
            new_offset, new_gain, new_upper_level, clamp=True
        )
        self.dtype_params[self.current_dtype] = (clamped_offset, clamped_gain, clamped_upper_level)
        self._emit_brightness_changed()

        if not keep_settings:
            self._reset_to_initial()
            self._emit_brightness_changed()

    def _get_roi(self):
        """親の ROI を (x, y, w, h) で返す。ROI がない場合は None。"""
        if self.viewer and hasattr(self.viewer, "state"):
            r = self.viewer.state.roi
            if r and not r.isEmpty():
                return r.x(), r.y(), r.width(), r.height()
            return None

    def _on_roi_changed(self, *args):
        if self.auto_scale_cb.isChecked() and self.use_roi_cb.isChecked():
            self.roi = self._get_roi()
            self._apply_autoscale()

    def _apply_autoscale(self):
        """表示中の channel の最小値・最大値を offset・upper level にする。ROI 使用時は ROI 内で求める。"""
        if self.roi is not None and self.use_roi_cb.isChecked():
            x, y, w, h = self.roi
            data = self.image_array[y : y + h, x : x + w, ...]
        else:
            data = self.image_array

        if self.image_array.ndim > 2:
            ch = self.viewer.channel_checks
            data = data[..., ch]
        val_min = np.min(data)
        val_max = np.max(data)

        self._apply_values(val_min, 1.0, val_max, clamp=True)
        self._emit_brightness_changed()
