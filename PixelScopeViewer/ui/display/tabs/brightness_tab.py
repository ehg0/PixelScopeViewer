"""brightness 調整 tab。"""

import math

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from PixelScopeViewer.core.brightness import (
    BrightnessParams,
    autoscale_range,
    determine_dtype_defaults,
    merged_dtype_defaults,
)
from PixelScopeViewer.core.constants import get_dtype_defaults
from PixelScopeViewer.ui.common.widgets import set_value_silently
from PixelScopeViewer.ui.display.tabs.logic import brightness_builder as builder
from PixelScopeViewer.ui.display.tabs.logic import clamp_value, round_to_power_of_2


class BrightnessTab(QWidget):
    """offset・gain・upper level を slider と spin box で調整する tab。"""

    brightness_changed = Signal(float, float, float)  # offset, gain, upper_level

    def __init__(self, parent=None, image_array=None, image_path=None):
        super().__init__(parent)
        self.viewer = parent.viewer

        self.image_array = image_array
        self.image_path = image_path

        # 親で ROI が変わったら auto scale をやり直す
        if self.viewer and hasattr(self.viewer, "roi_changed"):
            self.viewer.roi_changed.connect(self._on_roi_changed)

        # dtype ごとの (offset, gain, upper_level)
        self.dtype_params = {}
        # タイル比較モードでは brightness を全タイル共通の "tile" に保存する
        self.tile_mode = False

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
        set_value_silently(self.offset_spinbox, value)
        self._save_current_params()
        self._emit_brightness_changed()

    def _on_offset_spinbox_changed(self, value):
        set_value_silently(self.offset_slider, int(value))
        self._save_current_params()
        self._emit_brightness_changed()

    def _on_gain_slider_changed(self, value):
        # slider の値は log2(gain)
        actual_value = 2**value
        set_value_silently(self.gain_spinbox, actual_value)
        self._save_current_params()
        self._emit_brightness_changed()

    def _on_gain_spinbox_changed(self, value):
        # 最も近い 2 の累乗に丸める
        if value > 0:
            rounded = round_to_power_of_2(value, self._gain_log2_min, self._gain_log2_max)
            log2_value = round(math.log2(rounded))

            set_value_silently(self.gain_spinbox, rounded)

            set_value_silently(self.gain_slider, log2_value)

            self._save_current_params()
            self._emit_brightness_changed()
        else:
            self._reset_gain_to_default()

    def _on_upper_level_slider_changed(self, value):
        set_value_silently(self.upper_level_spinbox, value)
        self._save_current_params()
        self._emit_brightness_changed()

    def _on_upper_level_spinbox_changed(self, value):
        set_value_silently(self.upper_level_slider, int(value))
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
        """表示中の値（auto scale の結果を含む）を viewer の現在の dtype の設定に反映する。"""
        if self.viewer is not None:
            self.viewer.state.brightness_by_dtype[self.current_dtype] = BrightnessParams(*self.get_parameters())

    def _reset_gain_to_default(self):
        set_value_silently(self.gain_spinbox, 1.0)

        set_value_silently(self.gain_slider, 0)

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

    def set_tile_mode(self, dtype_keys: list[str] | None, params: BrightnessParams | None = None):
        """タイル比較モードの入力範囲と値にする。dtype_keys が None の場合は表示中の画像の dtype に戻す。

        Args:
            dtype_keys: 登録されている画像の dtype（先頭は初期値に使う最初のタイルの画像の dtype）。
            params: 全タイル共通の brightness。
        """
        if dtype_keys is None:
            if not self.tile_mode:
                return
            self.tile_mode = False
            self.dtype_combo.setEnabled(True)
            self.dtype_combo.setToolTip("")
            self.current_dtype = None
            self.update_for_new_image(self.image_array, self.image_path, keep_settings=True)
            return

        self.tile_mode = True
        merged = merged_dtype_defaults(dtype_keys)
        self.current_dtype = "tile"
        self.is_float_type = merged["is_float_type"]
        self.initial_offset = merged["initial_offset"]
        self.initial_gain = merged["initial_gain"]
        self.initial_upper_level = merged["initial_upper_level"]
        self.offset_range = merged["offset_range"]
        self.upper_level_range = merged["upper_level_range"]
        self.dtype_combo.setEnabled(False)
        self.dtype_combo.setToolTip("タイル比較モードでは全タイル共通の値を使います")
        self._configure_offset_widgets()
        self._configure_gain_widgets()
        self._configure_upper_level_widgets()
        if params is None:
            params = BrightnessParams(self.initial_offset, self.initial_gain, self.initial_upper_level)
        self.dtype_params["tile"] = self._apply_values(params.offset, params.gain, params.upper_level, clamp=True)
        if self.auto_scale_cb.isChecked():
            self._apply_autoscale()
        else:
            self._emit_brightness_changed()

    def update_for_new_image(self, image_array=None, image_path=None, keep_settings=True):
        """新しい画像の dtype に合わせて入力範囲と値を更新する。

        タイル比較モードでは入力範囲と値を変えず、auto scale の対象の画像だけを替える。

        Args:
            image_array: 画像配列。None は画像がない（空欄のタイルが active）場合。
            image_path: 画像ファイルのパス。
            keep_settings: dtype ごとに保存した設定を使うか。False の場合は初期値に戻す。
        """
        if self.tile_mode:
            self.image_array = image_array
            self.image_path = image_path
            if self.auto_scale_cb.isChecked():
                self._apply_autoscale()
            return

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

        if keep_settings and old_dtype is not None:
            self.dtype_params[old_dtype] = old_params

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
        if self.viewer is not None:
            r = self.viewer.state.roi
            if r and not r.isEmpty():
                return r.x(), r.y(), r.width(), r.height()
            return None

    def _on_roi_changed(self, *args):
        if self.auto_scale_cb.isChecked() and self.use_roi_cb.isChecked():
            self._apply_autoscale()

    def _apply_autoscale(self):
        """表示中の channel の最小値・最大値を offset・upper level にする。ROI 使用時は ROI 内で求める。

        ROI が画像の範囲外などで計算できない場合は、直前の値を引き継ぐ。
        """
        if self.image_array is None:
            return
        # ROI は控えずに毎回 viewer から読む（auto scale を ON にする前に作った ROI も使う）
        roi = self._get_roi() if self.use_roi_cb.isChecked() else None
        checks = self.viewer.channel_checks if self.image_array.ndim > 2 else None
        result = autoscale_range(self.image_array, roi, checks)
        if result is None:
            return
        val_min, val_max = result

        self._apply_values(val_min, 1.0, val_max, clamp=True)
        self._emit_brightness_changed()
