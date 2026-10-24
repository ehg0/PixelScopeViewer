import math

import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from PixelScopeViewer.core.constants import get_dtype_defaults

from .logic import clamp_value, determine_dtype_defaults, round_to_power_of_2
from .logic.brightness_builder import BrightnessUIBuilder


class BrightnessTab(QWidget):
    """Tab for adjusting display brightness parameters.

    Emits:
        brightness_changed(float, float, float): (offset, gain, upper_level)
    """

    brightness_changed = Signal(float, float, float)  # offset, gain, upper_level

    def __init__(self, parent=None, image_array=None, image_path=None):
        super().__init__(parent)
        self.viewer = parent.viewer

        self.image_array = image_array
        self.image_path = image_path

        self.roi = self._get_roi()
        # 親側でROIが切り直されたときにROIを取得
        if self.viewer and hasattr(self.viewer, "roi_changed"):
            self.viewer.roi_changed.connect(self._on_roi_changed)

        # Storage for per-dtype parameters: {dtype_key: (offset, gain, upper_level)}
        self.dtype_params = {}

        # Determine initial values based on image type using helper function
        defaults = determine_dtype_defaults(image_array)
        self.current_dtype = defaults["dtype_key"]
        self.is_float_type = defaults["is_float_type"]
        self.initial_offset = defaults["initial_offset"]
        self.initial_gain = defaults["initial_gain"]
        self.initial_upper_level = defaults["initial_upper_level"]
        self.offset_range = defaults["offset_range"]
        self.upper_level_range = defaults["upper_level_range"]

        # Extended ranges for controls
        self._gain_log2_min = -7  # 2^-7 = 1/128
        self._gain_log2_max = 10  # 2^10 = 1024
        self._gain_spinbox_min = 2**-7
        self._gain_spinbox_max = 1024.0

        # Build UI
        self._build_ui()

        # Set initial values and save to dtype_params
        self._reset_to_initial()

    # ------------------------ UI building ------------------------
    def _build_ui(self):
        """Build the entire UI using BrightnessUIBuilder."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(25, 25, 25, 25)

        builder = BrightnessUIBuilder(self)

        # Dtype selector
        self.dtype_combo = builder.build_dtype_selector(main_layout, self.current_dtype, self._on_dtype_changed)

        # Auto Scale
        self.auto_scale_cb, self.use_roi_cb, self.set_as_default = builder.build_autoscale(
            main_layout, self._on_autoscale_changed, self._save_current_params
        )

        # Offset controls
        self.offset_slider, self.offset_spinbox = builder.build_offset_controls(
            main_layout,
            self.initial_offset,
            self.offset_range,
            self.is_float_type,
            self._on_offset_slider_changed,
            self._on_offset_spinbox_changed,
        )

        # Gain controls
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

        # Upper_level controls
        self.upper_level_slider, self.upper_level_spinbox = builder.build_upper_level_controls(
            main_layout,
            self.initial_upper_level,
            self.upper_level_range,
            self.is_float_type,
            self._on_upper_level_slider_changed,
            self._on_upper_level_spinbox_changed,
        )

        # Formula and reset button
        self.reset_button = builder.build_formula_and_reset(main_layout, self._on_reset_clicked)

    # ------------------------ Slot handlers ------------------------
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
        # Slider value is log2, convert to actual gain (power of 2)
        actual_value = 2**value
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(actual_value)
        self.gain_spinbox.blockSignals(False)
        self._save_current_params()
        self._emit_brightness_changed()

    def _on_gain_spinbox_changed(self, value):
        # Round to nearest power of 2
        if value > 0:
            rounded = round_to_power_of_2(value, self._gain_log2_min, self._gain_log2_max)
            log2_value = round(math.log2(rounded))

            # Update spinbox and slider
            self.gain_spinbox.blockSignals(True)
            self.gain_spinbox.setValue(rounded)
            self.gain_spinbox.blockSignals(False)

            self.gain_slider.blockSignals(True)
            self.gain_slider.setValue(log2_value)
            self.gain_slider.blockSignals(False)

            self._save_current_params()
            self._emit_brightness_changed()
        else:
            # Handle invalid input
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
        """Handle manual dtype selection from combo box."""
        # Save current params for the old dtype
        prev_dtype = self.current_dtype
        prev_params = (
            self.offset_spinbox.value(),
            self.gain_spinbox.value(),
            self.upper_level_spinbox.value(),
        )
        self._save_current_params()

        # Switch to new dtype and update ranges/widgets
        self.current_dtype = dtype_text
        self._update_ranges_for_dtype(dtype_text)
        self._configure_offset_widgets()
        self._configure_gain_widgets()
        self._configure_upper_level_widgets()

        # Prefer using saved params for the new dtype; if none, carry over previous params
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

    # ------------------------ Range and widget configuration ------------------------
    def _update_ranges_for_dtype(self, dtype_key):
        """Update is_float_type and ranges based on dtype key."""
        defaults = get_dtype_defaults(dtype_key)
        self.is_float_type = defaults["is_float_type"]
        self.offset_range = defaults["offset_range"]
        self.upper_level_range = defaults["upper_level_range"]

    def _get_params_for_dtype(self, dtype_key):
        """Return (offset, gain, upper_level) for dtype: saved if available, else defaults."""
        if dtype_key in self.dtype_params:
            return self.dtype_params[dtype_key]
        defaults = get_dtype_defaults(dtype_key)
        return (defaults["initial_offset"], defaults["initial_gain"], defaults["initial_upper_level"])

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
        """Configure gain slider/spinbox ranges."""
        self.gain_slider.blockSignals(True)
        self.gain_slider.setRange(self._gain_log2_min, self._gain_log2_max)
        self.gain_slider.blockSignals(False)

        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setRange(self._gain_spinbox_min, self._gain_spinbox_max)
        self.gain_spinbox.blockSignals(False)

    def _apply_values(self, offset, gain, upper_level, clamp=True):
        """Apply values to all widgets, optionally clamping them to valid ranges.

        Returns:
            tuple: (actual_offset, actual_gain, actual_upper_level) after clamping and rounding
        """
        if clamp:
            offset = clamp_value(offset, self.offset_range[0], self.offset_range[1])
            gain = clamp_value(gain, self._gain_spinbox_min, self._gain_spinbox_max)
            gain = round_to_power_of_2(gain, self._gain_log2_min, self._gain_log2_max)
            upper_level = clamp_value(upper_level, self.upper_level_range[0], self.upper_level_range[1])
        else:
            gain = round_to_power_of_2(gain, self._gain_log2_min, self._gain_log2_max)

        gain_log2 = round(math.log2(gain))

        # Offset
        self.offset_slider.blockSignals(True)
        self.offset_spinbox.blockSignals(True)
        self.offset_spinbox.setValue(offset)
        self.offset_slider.setValue(int(offset))
        self.offset_slider.blockSignals(False)
        self.offset_spinbox.blockSignals(False)

        # Gain
        self.gain_slider.blockSignals(True)
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(gain)
        self.gain_slider.setValue(gain_log2)
        self.gain_slider.blockSignals(False)
        self.gain_spinbox.blockSignals(False)

        # Upper_level
        self.upper_level_slider.blockSignals(True)
        self.upper_level_spinbox.blockSignals(True)
        self.upper_level_spinbox.setValue(upper_level)
        self.upper_level_slider.setValue(int(upper_level))
        self.upper_level_slider.blockSignals(False)
        self.upper_level_spinbox.blockSignals(False)

        return offset, gain, upper_level

    # ------------------------ State management ------------------------
    def _save_current_params(self):
        """Save current widget values to dtype_params."""
        current_params = (
            self.offset_spinbox.value(),
            self.gain_spinbox.value(),
            self.upper_level_spinbox.value(),
        )
        self.dtype_params[self.current_dtype] = current_params

    def _sync_to_manager(self):
        """Sync current dialog dtype params to the viewer's brightness_manager storage."""
        try:
            dialog = self.parent()
            if dialog and hasattr(dialog, "parent") and callable(dialog.parent):
                viewer = dialog.parent()
                if viewer and hasattr(viewer, "brightness_manager"):
                    mgr = viewer.brightness_manager
                    offset, gain, upper_level = self.dtype_params.get(self.current_dtype, (0, 1.0, 255))
                    mgr._params_by_dtype[self.current_dtype] = (offset, gain, upper_level)
        except Exception:
            pass

    def _reset_gain_to_default(self):
        """Reset gain to 1.0 when invalid value entered."""
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(1.0)
        self.gain_spinbox.blockSignals(False)

        self.gain_slider.blockSignals(True)
        self.gain_slider.setValue(0)
        self.gain_slider.blockSignals(False)

        self._save_current_params()
        self._emit_brightness_changed()

    # ------------------------ Public API ------------------------
    def _emit_brightness_changed(self):
        """Emit brightness_changed signal with current values."""
        offset = self.offset_spinbox.value()
        gain = self.gain_spinbox.value()
        upper_level = self.upper_level_spinbox.value()
        self.brightness_changed.emit(offset, gain, upper_level)
        self._sync_to_manager()

    def set_gain(self, gain_value):
        """Set gain value programmatically.

        Args:
            gain_value: Desired gain value (will be rounded to power of 2)
        """
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
        """Reset all parameters to initial values."""
        self._reset_to_initial()
        self._save_current_params()
        self._emit_brightness_changed()

    def _reset_to_initial(self):
        """Reset widgets to initial values."""
        rounded_gain = round_to_power_of_2(self.initial_gain, self._gain_log2_min, self._gain_log2_max)
        gain_log2 = round(math.log2(rounded_gain))

        # Offset
        self.offset_slider.blockSignals(True)
        self.offset_spinbox.blockSignals(True)
        self.offset_spinbox.setValue(self.initial_offset)
        self.offset_slider.setValue(int(self.initial_offset))
        self.offset_slider.blockSignals(False)
        self.offset_spinbox.blockSignals(False)

        # Gain
        self.gain_slider.blockSignals(True)
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(rounded_gain)
        self.gain_slider.setValue(gain_log2)
        self.gain_slider.blockSignals(False)
        self.gain_spinbox.blockSignals(False)

        # Upper_level
        self.upper_level_slider.blockSignals(True)
        self.upper_level_spinbox.blockSignals(True)
        self.upper_level_spinbox.setValue(self.initial_upper_level)
        self.upper_level_slider.setValue(int(self.initial_upper_level))
        self.upper_level_slider.blockSignals(False)
        self.upper_level_spinbox.blockSignals(False)

        self.dtype_params[self.current_dtype] = (self.initial_offset, rounded_gain, self.initial_upper_level)

    def get_parameters(self):
        """Get current brightness parameters.

        Returns:
            tuple: (offset, gain, upper_level)
        """
        return (
            self.offset_spinbox.value(),
            self.gain_spinbox.value(),
            self.upper_level_spinbox.value(),
        )

    def update_for_new_image(self, image_array=None, image_path=None, keep_settings=True):
        """Update tab for a new image.

        Args:
            image_array: New image array
            image_path: New image path
            keep_settings: Whether to preserve current settings
        """
        old_dtype = self.current_dtype
        old_params = (
            self.offset_spinbox.value(),
            self.gain_spinbox.value(),
            self.upper_level_spinbox.value(),
        )

        self.image_array = image_array
        self.image_path = image_path
        old_is_float = self.is_float_type

        # auto scaleする場合。早期return
        if self.auto_scale_cb.isChecked():
            self._apply_autoscale()
            return

        # Determine new defaults
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

        # Update dtype combo
        if hasattr(self, "dtype_combo"):
            self.dtype_combo.blockSignals(True)
            self.dtype_combo.setCurrentText(self.current_dtype)
            self.dtype_combo.blockSignals(False)

        # Determine values to use
        if keep_settings and self.current_dtype in self.dtype_params:
            new_offset, new_gain, new_upper_level = self.dtype_params[self.current_dtype]
        else:
            new_offset = self.initial_offset
            new_gain = self.initial_gain
            new_upper_level = self.initial_upper_level

        # Reconfigure widgets
        self._configure_offset_widgets()
        self._configure_gain_widgets()
        self._configure_upper_level_widgets()

        # Apply values
        clamped_offset, clamped_gain, clamped_upper_level = self._apply_values(
            new_offset, new_gain, new_upper_level, clamp=True
        )
        self.dtype_params[self.current_dtype] = (clamped_offset, clamped_gain, clamped_upper_level)
        self._emit_brightness_changed()

        if not keep_settings:
            self._reset_to_initial()
            self._emit_brightness_changed()

    def _get_roi(self):
        """親の current_roi_rect からROIを取得する"""
        if self.viewer and hasattr(self.viewer, "current_roi_rect"):
            r = self.viewer.current_roi_rect
            if r and not r.isEmpty():
                return r.x(), r.y(), r.width(), r.height()
            return None

    def _on_roi_changed(self, *args):
        """親側でROIが変更されたときにROIを更新する"""
        if self.auto_scale_cb.isChecked() and self.use_roi_cb.isChecked():
            self.roi = self._get_roi()
            self._apply_autoscale()

    def _apply_autoscale(self):
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
