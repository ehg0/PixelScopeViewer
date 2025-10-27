import math
import numpy as np
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout

from .components import PowerOfTwoSpinBox
from .logic import (
    determine_dtype_defaults,
    get_dtype_defaults,
    round_to_power_of_2,
    format_value_label,
    format_gain_label,
    clamp_value,
)
from .logic.brightness_builder import BrightnessUIBuilder


class BrightnessTab(QWidget):
    """Tab for adjusting display brightness parameters.

    Emits:
        brightness_changed(float, float, float): (offset, gain, saturation)
    """

    brightness_changed = Signal(float, float, float)  # offset, gain, saturation

    def __init__(self, parent=None, image_array=None, image_path=None):
        super().__init__(parent)
        self.image_array = image_array
        self.image_path = image_path

        # Storage for per-dtype parameters: {dtype_key: (offset, gain, saturation)}
        self.dtype_params = {}

        # Determine initial values based on image type using helper function
        defaults = determine_dtype_defaults(image_array, image_path)
        self.current_dtype = defaults["dtype_key"]
        self.is_float_type = defaults["is_float_type"]
        self.initial_offset = defaults["initial_offset"]
        self.initial_gain = defaults["initial_gain"]
        self.initial_saturation = defaults["initial_saturation"]
        self.offset_range = defaults["offset_range"]
        self.gain_range = defaults["gain_range"]
        self.saturation_range = defaults["saturation_range"]

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

        # Offset controls
        self.offset_value_label, self.offset_slider, self.offset_spinbox = builder.build_offset_controls(
            main_layout,
            self.initial_offset,
            self.offset_range,
            self.is_float_type,
            self._on_offset_slider_changed,
            self._on_offset_spinbox_changed,
        )

        # Gain controls
        self.gain_value_label, self.gain_slider, self.gain_spinbox = builder.build_gain_controls(
            main_layout,
            self.initial_gain,
            self._gain_log2_min,
            self._gain_log2_max,
            self._gain_spinbox_min,
            self._gain_spinbox_max,
            self._on_gain_slider_changed,
            self._on_gain_spinbox_changed,
        )

        # Saturation controls
        (
            self.saturation_value_label,
            self.saturation_slider,
            self.saturation_spinbox,
        ) = builder.build_saturation_controls(
            main_layout,
            self.initial_saturation,
            self.saturation_range,
            self.is_float_type,
            self._on_saturation_slider_changed,
            self._on_saturation_spinbox_changed,
        )

        # Formula and reset button
        self.reset_button = builder.build_formula_and_reset(main_layout, self._on_reset_clicked)

    # ------------------------ Slot handlers ------------------------
    def _on_offset_slider_changed(self, value):
        actual_value = value / 10.0
        self.offset_spinbox.blockSignals(True)
        self.offset_spinbox.setValue(actual_value)
        self.offset_spinbox.blockSignals(False)
        self._update_offset_label(actual_value)
        self._save_current_params()
        self._emit_brightness_changed()

    def _on_offset_spinbox_changed(self, value):
        self.offset_slider.blockSignals(True)
        self.offset_slider.setValue(int(value * 10))
        self.offset_slider.blockSignals(False)
        self._update_offset_label(value)
        self._save_current_params()
        self._emit_brightness_changed()

    def _on_gain_slider_changed(self, value):
        # Slider value is log2, convert to actual gain (power of 2)
        actual_value = 2**value
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(actual_value)
        self.gain_spinbox.blockSignals(False)
        self._update_gain_label(actual_value)
        self._save_current_params()
        self._emit_brightness_changed()

    def _on_gain_spinbox_changed(self, value):
        # Round to nearest power of 2
        if value > 0:
            rounded = round_to_power_of_2(value, self._gain_log2_min, self._gain_log2_max)
            log2_value = int(round(math.log2(rounded)))

            # Update spinbox and slider
            self.gain_spinbox.blockSignals(True)
            self.gain_spinbox.setValue(rounded)
            self.gain_spinbox.blockSignals(False)

            self.gain_slider.blockSignals(True)
            self.gain_slider.setValue(log2_value)
            self.gain_slider.blockSignals(False)

            self._update_gain_label(rounded)
            self._save_current_params()
            self._emit_brightness_changed()
        else:
            # Handle invalid input
            self._reset_gain_to_default()

    def _on_saturation_slider_changed(self, value):
        actual_value = value / 1000.0 if self.is_float_type else value
        self.saturation_spinbox.blockSignals(True)
        self.saturation_spinbox.setValue(actual_value)
        self.saturation_spinbox.blockSignals(False)
        self._update_saturation_label(actual_value)
        self._save_current_params()
        self._emit_brightness_changed()

    def _on_saturation_spinbox_changed(self, value):
        self.saturation_slider.blockSignals(True)
        self.saturation_slider.setValue(int(value * 1000) if self.is_float_type else int(value))
        self.saturation_slider.blockSignals(False)
        self._update_saturation_label(value)
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
            self.saturation_spinbox.value(),
        )
        self._save_current_params()

        # Switch to new dtype and update ranges/widgets
        self.current_dtype = dtype_text
        self._update_ranges_for_dtype(dtype_text)
        self._configure_offset_widgets()
        self._configure_gain_widgets()
        self._configure_saturation_widgets()

        # Prefer using saved params for the new dtype; if none, carry over previous params
        if dtype_text in self.dtype_params:
            offset, gain, saturation = self.dtype_params[dtype_text]
        else:
            offset, gain, saturation = prev_params

        clamped_offset, clamped_gain, clamped_sat = self._apply_values(offset, gain, saturation, clamp=True)
        self.dtype_params[self.current_dtype] = (clamped_offset, clamped_gain, clamped_sat)
        self._emit_brightness_changed()

    # ------------------------ Label updates ------------------------
    def _update_offset_label(self, value):
        self.offset_value_label.setText(format_value_label(value, self.is_float_type))

    def _update_gain_label(self, value):
        self.gain_value_label.setText(format_gain_label(value))

    def _update_saturation_label(self, value):
        self.saturation_value_label.setText(format_value_label(value, self.is_float_type))

    # ------------------------ Range and widget configuration ------------------------
    def _update_ranges_for_dtype(self, dtype_key):
        """Update is_float_type and ranges based on dtype key."""
        defaults = get_dtype_defaults(dtype_key)
        self.is_float_type = defaults["is_float_type"]
        self.offset_range = defaults["offset_range"]
        self.saturation_range = defaults["saturation_range"]
        self.gain_range = defaults["gain_range"]

    def _get_params_for_dtype(self, dtype_key):
        """Return (offset, gain, saturation) for dtype: saved if available, else defaults."""
        if dtype_key in self.dtype_params:
            return self.dtype_params[dtype_key]
        defaults = get_dtype_defaults(dtype_key)
        return (defaults["initial_offset"], defaults["initial_gain"], defaults["initial_saturation"])

    def _configure_offset_widgets(self):
        self.offset_slider.blockSignals(True)
        self.offset_slider.setRange(int(self.offset_range[0] * 10), int(self.offset_range[1] * 10))
        self.offset_slider.blockSignals(False)
        self.offset_spinbox.blockSignals(True)
        self.offset_spinbox.setRange(self.offset_range[0], self.offset_range[1])
        if self.is_float_type:
            self.offset_spinbox.setDecimals(5)
            self.offset_spinbox.setSingleStep(0.01)
        else:
            self.offset_spinbox.setDecimals(0)
            self.offset_spinbox.setSingleStep(1)
        self.offset_spinbox.blockSignals(False)

    def _configure_saturation_widgets(self):
        self.saturation_slider.blockSignals(True)
        if self.is_float_type:
            self.saturation_slider.setRange(int(self.saturation_range[0] * 1000), int(self.saturation_range[1] * 1000))
        else:
            self.saturation_slider.setRange(self.saturation_range[0], self.saturation_range[1])
        self.saturation_slider.blockSignals(False)
        self.saturation_spinbox.blockSignals(True)
        self.saturation_spinbox.setRange(self.saturation_range[0], self.saturation_range[1])
        if self.is_float_type:
            self.saturation_spinbox.setDecimals(5)
            self.saturation_spinbox.setSingleStep(0.01)
        else:
            self.saturation_spinbox.setDecimals(0)
            self.saturation_spinbox.setSingleStep(1)
        self.saturation_spinbox.blockSignals(False)

    def _configure_gain_widgets(self):
        """Configure gain slider/spinbox ranges."""
        self.gain_slider.blockSignals(True)
        self.gain_slider.setRange(self._gain_log2_min, self._gain_log2_max)
        self.gain_slider.blockSignals(False)

        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setRange(self._gain_spinbox_min, self._gain_spinbox_max)
        self.gain_spinbox.blockSignals(False)

    def _apply_values(self, offset, gain, saturation, clamp=True):
        """Apply values to all widgets, optionally clamping them to valid ranges.

        Returns:
            tuple: (actual_offset, actual_gain, actual_saturation) after clamping and rounding
        """
        if clamp:
            offset = clamp_value(offset, self.offset_range[0], self.offset_range[1])
            gain = clamp_value(gain, self._gain_spinbox_min, self._gain_spinbox_max)
            gain = round_to_power_of_2(gain, self._gain_log2_min, self._gain_log2_max)
            saturation = clamp_value(saturation, self.saturation_range[0], self.saturation_range[1])
        else:
            gain = round_to_power_of_2(gain, self._gain_log2_min, self._gain_log2_max)

        gain_log2 = int(round(math.log2(gain)))

        # Offset
        self.offset_slider.blockSignals(True)
        self.offset_spinbox.blockSignals(True)
        self.offset_spinbox.setValue(offset)
        self.offset_slider.setValue(int(offset * 10))
        self._update_offset_label(offset)
        self.offset_slider.blockSignals(False)
        self.offset_spinbox.blockSignals(False)

        # Gain
        self.gain_slider.blockSignals(True)
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(gain)
        self.gain_slider.setValue(gain_log2)
        self._update_gain_label(gain)
        self.gain_slider.blockSignals(False)
        self.gain_spinbox.blockSignals(False)

        # Saturation
        self.saturation_slider.blockSignals(True)
        self.saturation_spinbox.blockSignals(True)
        self.saturation_spinbox.setValue(saturation)
        self.saturation_slider.setValue(int(saturation * 1000) if self.is_float_type else int(saturation))
        self._update_saturation_label(saturation)
        self.saturation_slider.blockSignals(False)
        self.saturation_spinbox.blockSignals(False)

        return offset, gain, saturation

    # ------------------------ State management ------------------------
    def _save_current_params(self):
        """Save current widget values to dtype_params."""
        current_params = (
            self.offset_spinbox.value(),
            self.gain_spinbox.value(),
            self.saturation_spinbox.value(),
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
                    offset, gain, saturation = self.dtype_params.get(self.current_dtype, (0, 1.0, 255))
                    mgr._params_by_dtype[self.current_dtype] = (offset, gain, saturation)
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

        self._update_gain_label(1.0)
        self._save_current_params()
        self._emit_brightness_changed()

    # ------------------------ Public API ------------------------
    def _emit_brightness_changed(self):
        """Emit brightness_changed signal with current values."""
        offset = self.offset_spinbox.value()
        gain = self.gain_spinbox.value()
        saturation = self.saturation_spinbox.value()
        self.brightness_changed.emit(offset, gain, saturation)
        self._sync_to_manager()

    def set_gain(self, gain_value):
        """Set gain value programmatically.

        Args:
            gain_value: Desired gain value (will be rounded to power of 2)
        """
        rounded = round_to_power_of_2(gain_value, self._gain_log2_min, self._gain_log2_max)
        log2_value = int(round(math.log2(rounded)))

        self.gain_slider.blockSignals(True)
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(rounded)
        self.gain_slider.setValue(log2_value)
        self._update_gain_label(rounded)
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
        gain_log2 = int(round(math.log2(rounded_gain)))

        # Offset
        self.offset_slider.blockSignals(True)
        self.offset_spinbox.blockSignals(True)
        self.offset_spinbox.setValue(self.initial_offset)
        self.offset_slider.setValue(int(self.initial_offset * 10))
        self._update_offset_label(self.initial_offset)
        self.offset_slider.blockSignals(False)
        self.offset_spinbox.blockSignals(False)

        # Gain
        self.gain_slider.blockSignals(True)
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(rounded_gain)
        self.gain_slider.setValue(gain_log2)
        self._update_gain_label(rounded_gain)
        self.gain_slider.blockSignals(False)
        self.gain_spinbox.blockSignals(False)

        # Saturation
        self.saturation_slider.blockSignals(True)
        self.saturation_spinbox.blockSignals(True)
        self.saturation_spinbox.setValue(self.initial_saturation)
        self.saturation_slider.setValue(
            int(self.initial_saturation * 1000) if self.is_float_type else int(self.initial_saturation)
        )
        self._update_saturation_label(self.initial_saturation)
        self.saturation_slider.blockSignals(False)
        self.saturation_spinbox.blockSignals(False)

        self.dtype_params[self.current_dtype] = (self.initial_offset, rounded_gain, self.initial_saturation)

    def get_parameters(self):
        """Get current brightness parameters.

        Returns:
            tuple: (offset, gain, saturation)
        """
        return (
            self.offset_spinbox.value(),
            self.gain_spinbox.value(),
            self.saturation_spinbox.value(),
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
            self.saturation_spinbox.value(),
        )

        self.image_array = image_array
        self.image_path = image_path
        old_is_float = self.is_float_type

        # Determine new defaults
        defaults = determine_dtype_defaults(image_array, image_path)
        self.current_dtype = defaults["dtype_key"]
        self.is_float_type = defaults["is_float_type"]
        self.initial_offset = defaults["initial_offset"]
        self.initial_gain = defaults["initial_gain"]
        self.initial_saturation = defaults["initial_saturation"]
        self.offset_range = defaults["offset_range"]
        self.gain_range = defaults["gain_range"]
        self.saturation_range = defaults["saturation_range"]

        if keep_settings:
            self.dtype_params[old_dtype] = old_params

        # Update dtype combo
        if hasattr(self, "dtype_combo"):
            self.dtype_combo.blockSignals(True)
            self.dtype_combo.setCurrentText(self.current_dtype)
            self.dtype_combo.blockSignals(False)

        # Determine values to use
        if keep_settings and self.current_dtype in self.dtype_params:
            new_offset, new_gain, new_saturation = self.dtype_params[self.current_dtype]
        else:
            new_offset = self.initial_offset
            new_gain = self.initial_gain
            new_saturation = self.initial_saturation

        # Reconfigure widgets
        self._configure_offset_widgets()
        self._configure_gain_widgets()
        self._configure_saturation_widgets()

        # Apply values
        clamped_offset, clamped_gain, clamped_sat = self._apply_values(new_offset, new_gain, new_saturation, clamp=True)
        self.dtype_params[self.current_dtype] = (clamped_offset, clamped_gain, clamped_sat)
        self._emit_brightness_changed()

        if not keep_settings:
            self._reset_to_initial()
            self._emit_brightness_changed()
