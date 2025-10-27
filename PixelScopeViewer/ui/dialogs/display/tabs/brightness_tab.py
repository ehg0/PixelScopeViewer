import math
import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QDoubleSpinBox,
    QPushButton,
    QSpinBox,
    QComboBox,
)


class PowerOfTwoSpinBox(QDoubleSpinBox):
    """Custom spin box that steps by powers of 2."""

    def __init__(self, parent=None, log2_min=-7, log2_max=10):
        super().__init__(parent)
        self._log2_min = log2_min
        self._log2_max = log2_max

    def stepBy(self, steps):
        """Override to step by powers of 2."""
        current_value = self.value()
        if current_value <= 0:
            current_value = 1.0

        # Get current log2 value
        current_log2 = math.log2(current_value)

        # Round to nearest integer and apply steps
        current_log2_int = round(current_log2)
        new_log2 = current_log2_int + steps

        # Clamp to valid range
        new_log2 = max(self._log2_min, min(self._log2_max, new_log2))

        # Convert back to actual value
        new_value = 2**new_log2

        # Set the new value (this will trigger valueChanged signal)
        self.setValue(new_value)

    def textFromValue(self, value):
        """Override to display optimal decimal places for powers of 2."""
        if value <= 0:
            # Handle invalid values
            return "0"

        if value >= 1.0:
            # For values >= 1, display as integer
            return f"{int(value)}"
        else:
            # For fractional values (< 1), calculate minimal decimal places needed
            # Powers of 2 less than 1: 0.5, 0.25, 0.125, 0.0625, etc.
            log2_val = math.log2(value)
            decimals = max(1, abs(int(log2_val)))
            return f"{value:.{decimals}f}".rstrip("0").rstrip(".")


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
        self.current_dtype = "uint8"  # Will be updated by _determine_initial_values

        # Determine initial values based on image type
        self._determine_initial_values()

        # Extended ranges for controls
        self._gain_slider_min, self._gain_slider_max = self.gain_range
        self._gain_spinbox_min = 2**-7  # 1/128
        self._gain_spinbox_max = 1024.0

        # Log2 slider range for binary steps (powers of 2)
        self._gain_log2_min = -7  # 2^-7 = 1/128
        self._gain_log2_max = 10  # 2^10 = 1024

        # Build UI
        self._build_ui()

        # Set initial values and save to dtype_params
        self._reset_to_initial()

    # ------------------------ init helpers ------------------------
    def _determine_initial_values(self):
        self.current_dtype = "uint8"
        self.initial_offset = 0
        self.initial_gain = 1.0
        self.initial_saturation = 255

        self.is_float_type = False
        self.offset_range = (-255, 255)
        self.gain_range = (0.1, 10.0)
        self.saturation_range = (1, 255)

        if self.image_path and self.image_path.lower().endswith(".bin"):
            self.initial_saturation = 1023
            self.saturation_range = (1, 4095)
            self.offset_range = (-1023, 1023)

        if self.image_array is not None:
            dtype = self.image_array.dtype
            if np.issubdtype(dtype, np.floating):
                self.current_dtype = "float"
                self.is_float_type = True
                self.initial_saturation = 1.0
                self.saturation_range = (0.001, 10.0)
                self.offset_range = (-1.0, 1.0)
                self.gain_range = (0.1, 10.0)
            elif np.issubdtype(dtype, np.integer):
                info = np.iinfo(dtype)
                max_val = info.max
                if max_val > 255:
                    self.current_dtype = "uint16"
                    self.initial_saturation = min(max_val, 4095)
                    self.saturation_range = (1, max_val)
                    self.offset_range = (-max_val // 2, max_val // 2)

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(25, 25, 25, 25)

        # dtype selector
        dtype_layout = QHBoxLayout()
        dtype_label = QLabel("データ型 (Data Type):")
        dtype_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        self.dtype_combo = QComboBox()
        self.dtype_combo.addItems(["float", "uint8", "uint16"])
        self.dtype_combo.setCurrentText(self.current_dtype)
        self.dtype_combo.currentTextChanged.connect(self._on_dtype_changed)
        dtype_layout.addWidget(dtype_label)
        dtype_layout.addWidget(self.dtype_combo)
        dtype_layout.addStretch()
        main_layout.addLayout(dtype_layout)
        main_layout.addSpacing(10)

        # Offset label with value
        offset_label_layout = QHBoxLayout()
        offset_title_label = QLabel("オフセット (Offset)")
        offset_title_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        self.offset_value_label = QLabel(
            f"{self.initial_offset:.0f}" if not self.is_float_type else f"{self.initial_offset:.5f}"
        )
        self.offset_value_label.setStyleSheet("color: #555; font-size: 10pt;")
        offset_label_layout.addWidget(offset_title_label)
        offset_label_layout.addWidget(self.offset_value_label)
        offset_label_layout.addStretch()
        main_layout.addLayout(offset_label_layout)

        # Offset controls
        offset_control_layout = QHBoxLayout()
        offset_control_layout.setSpacing(10)
        offset_caption = QLabel("Offset")
        offset_caption.setStyleSheet("font-size: 9pt; color: #888; min-width: 50px;")
        offset_caption.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        offset_control_layout.addWidget(offset_caption)

        self.offset_slider = QSlider(Qt.Horizontal)
        self.offset_slider.setRange(int(self.offset_range[0] * 10), int(self.offset_range[1] * 10))
        self.offset_slider.setTickPosition(QSlider.TicksBelow)
        self.offset_slider.setTickInterval((self.offset_range[1] - self.offset_range[0]) // 4)
        self.offset_slider.setStyleSheet(
            """
            QSlider::groove:horizontal { background: #ddd; height: 6px; border-radius: 3px; }
            QSlider::handle:horizontal { background: #666; width: 16px; margin: -5px 0; border-radius: 8px; }
            QSlider::handle:horizontal:hover { background: #444; }
            """
        )
        self.offset_slider.blockSignals(True)
        self.offset_slider.setValue(int(self.initial_offset * 10))
        self.offset_slider.blockSignals(False)
        self.offset_slider.valueChanged.connect(self._on_offset_slider_changed)

        self.offset_spinbox = QDoubleSpinBox()
        if self.is_float_type:
            self.offset_spinbox.setDecimals(5)
            self.offset_spinbox.setSingleStep(0.01)
        else:
            self.offset_spinbox.setDecimals(0)
            self.offset_spinbox.setSingleStep(1)
        self.offset_spinbox.setReadOnly(False)
        self.offset_spinbox.setKeyboardTracking(True)
        self.offset_spinbox.setRange(self.offset_range[0], self.offset_range[1])
        self.offset_spinbox.setStyleSheet("QSpinBox, QDoubleSpinBox { padding: 10px; font-size: 10pt; }")
        self.offset_spinbox.blockSignals(True)
        self.offset_spinbox.setValue(self.initial_offset)
        self.offset_spinbox.blockSignals(False)
        self.offset_spinbox.valueChanged.connect(self._on_offset_spinbox_changed)

        offset_control_layout.addWidget(self.offset_slider, 4)
        offset_control_layout.addWidget(self.offset_spinbox, 1)
        main_layout.addLayout(offset_control_layout)

        # Gain label with value
        gain_label_layout = QHBoxLayout()
        gain_title_label = QLabel("ゲイン (Gain)")
        gain_title_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        gain_title_label.setToolTip("ゲイン×0.5 : <,  ゲイン×2 : >")
        self.gain_value_label = QLabel(f"{self.initial_gain:.2f}")
        self.gain_value_label.setStyleSheet("color: #555; font-size: 10pt;")
        gain_label_layout.addWidget(gain_title_label)
        gain_label_layout.addWidget(self.gain_value_label)
        gain_label_layout.addStretch()
        main_layout.addLayout(gain_label_layout)

        # Gain controls
        gain_control_layout = QHBoxLayout()
        gain_caption = QLabel("Gain")
        gain_caption.setStyleSheet("font-size: 9pt; color: #888; min-width: 50px;")
        gain_caption.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        gain_control_layout.addWidget(gain_caption)

        self.gain_slider = QSlider(Qt.Horizontal)
        # Use log2 scale with integer steps for binary gain values
        self.gain_slider.setRange(self._gain_log2_min, self._gain_log2_max)
        self.gain_slider.setTickPosition(QSlider.TicksBelow)
        self.gain_slider.setTickInterval(1)  # Each tick is a power of 2
        self.gain_slider.setStyleSheet(
            """
            QSlider::groove:horizontal { background: #ddd; height: 6px; border-radius: 3px; }
            QSlider::handle:horizontal { background: #666; width: 16px; margin: -5px 0; border-radius: 8px; }
            QSlider::handle:horizontal:hover { background: #444; }
            """
        )
        self.gain_slider.blockSignals(True)
        # Convert initial gain to log2 value
        import math

        initial_log2 = int(round(math.log2(self.initial_gain)))
        initial_log2 = max(self._gain_log2_min, min(self._gain_log2_max, initial_log2))
        self.gain_slider.setValue(initial_log2)
        self.gain_slider.blockSignals(False)
        self.gain_slider.valueChanged.connect(self._on_gain_slider_changed)

        self.gain_spinbox = PowerOfTwoSpinBox(log2_min=self._gain_log2_min, log2_max=self._gain_log2_max)
        self.gain_spinbox.setDecimals(7)  # Max decimals for 2^-7 = 0.0078125
        self.gain_spinbox.setSingleStep(1)  # This is not used due to stepBy override, but set for consistency
        self.gain_spinbox.setReadOnly(False)
        self.gain_spinbox.setKeyboardTracking(True)
        self.gain_spinbox.setRange(self._gain_spinbox_min, self._gain_spinbox_max)
        self.gain_spinbox.setFixedWidth(100)  # Set fixed width for compact display
        self.gain_spinbox.setStyleSheet("QSpinBox, QDoubleSpinBox { padding: 10px; font-size: 10pt; }")
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(self.initial_gain)
        self.gain_spinbox.blockSignals(False)
        self.gain_spinbox.valueChanged.connect(self._on_gain_spinbox_changed)

        gain_control_layout.addWidget(self.gain_slider, 4)
        gain_control_layout.addWidget(self.gain_spinbox, 1)
        main_layout.addLayout(gain_control_layout)

        # Saturation label with value
        saturation_label_layout = QHBoxLayout()
        saturation_title_label = QLabel("飽和レベル (Saturation)")
        saturation_title_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        self.saturation_value_label = QLabel(
            f"{self.initial_saturation:.0f}" if not self.is_float_type else f"{self.initial_saturation:.5f}"
        )
        self.saturation_value_label.setStyleSheet("color: #555; font-size: 10pt;")
        saturation_label_layout.addWidget(saturation_title_label)
        saturation_label_layout.addWidget(self.saturation_value_label)
        saturation_label_layout.addStretch()
        main_layout.addLayout(saturation_label_layout)

        # Saturation controls
        saturation_control_layout = QHBoxLayout()
        saturation_caption = QLabel("Saturation")
        saturation_caption.setStyleSheet("font-size: 9pt; color: #888; min-width: 50px;")
        saturation_caption.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        saturation_control_layout.addWidget(saturation_caption)

        self.saturation_slider = QSlider(Qt.Horizontal)
        self.saturation_slider.setTickPosition(QSlider.TicksBelow)
        self.saturation_slider.setStyleSheet(
            """
            QSlider::groove:horizontal { background: #ddd; height: 6px; border-radius: 3px; }
            QSlider::handle:horizontal { background: #666; width: 16px; margin: -5px 0; border-radius: 8px; }
            QSlider::handle:horizontal:hover { background: #444; }
            """
        )
        if self.is_float_type:
            self.saturation_slider.setRange(int(self.saturation_range[0] * 1000), int(self.saturation_range[1] * 1000))
            self.saturation_slider.setTickInterval(
                int((self.saturation_range[1] - self.saturation_range[0]) * 1000 / 4)
            )
            self.saturation_slider.blockSignals(True)
            self.saturation_slider.setValue(int(self.initial_saturation * 1000))
            self.saturation_slider.blockSignals(False)
        else:
            self.saturation_slider.setRange(self.saturation_range[0], self.saturation_range[1])
            self.saturation_slider.setTickInterval((self.saturation_range[1] - self.saturation_range[0]) // 4)
            self.saturation_slider.blockSignals(True)
            self.saturation_slider.setValue(int(self.initial_saturation))
            self.saturation_slider.blockSignals(False)

        self.saturation_spinbox = QDoubleSpinBox()
        if self.is_float_type:
            self.saturation_spinbox.setDecimals(5)
            self.saturation_spinbox.setSingleStep(0.01)
        else:
            self.saturation_spinbox.setDecimals(0)
            self.saturation_spinbox.setSingleStep(1)
        self.saturation_spinbox.setReadOnly(False)
        self.saturation_spinbox.setKeyboardTracking(True)
        self.saturation_slider.valueChanged.connect(self._on_saturation_slider_changed)
        self.saturation_spinbox.setRange(self.saturation_range[0], self.saturation_range[1])
        self.saturation_spinbox.setStyleSheet("QSpinBox, QDoubleSpinBox { padding: 10px; font-size: 10pt; }")
        self.saturation_spinbox.blockSignals(True)
        self.saturation_spinbox.setValue(self.initial_saturation)
        self.saturation_spinbox.blockSignals(False)
        self.saturation_spinbox.valueChanged.connect(self._on_saturation_spinbox_changed)

        saturation_control_layout.addWidget(self.saturation_slider, 4)
        saturation_control_layout.addWidget(self.saturation_spinbox, 1)
        main_layout.addLayout(saturation_control_layout)

        formula_label = QLabel("-> yout = gain × (yin - offset) / saturation × 255")
        formula_label.setStyleSheet("font-style: italic; font-size: 10pt")
        main_layout.addWidget(formula_label)

        self.reset_button = QPushButton("Reset (Ctrl+R)")
        self.reset_button.clicked.connect(self._on_reset_clicked)
        main_layout.addWidget(self.reset_button)

        main_layout.addStretch()

    # ------------------------ slots & UI sync ------------------------
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
        import math

        # Round to nearest power of 2
        if value > 0:
            log2_value = math.log2(value)
            nearest_log2 = round(log2_value)
            nearest_log2 = max(self._gain_log2_min, min(self._gain_log2_max, nearest_log2))
            nearest_power_of_2 = 2**nearest_log2

            # Update spinbox to show the rounded power of 2
            self.gain_spinbox.blockSignals(True)
            self.gain_spinbox.setValue(nearest_power_of_2)
            self.gain_spinbox.blockSignals(False)

            # Update slider
            self.gain_slider.blockSignals(True)
            self.gain_slider.setValue(nearest_log2)
            self.gain_slider.blockSignals(False)

            self._update_gain_label(nearest_power_of_2)
            self._save_current_params()
            self._emit_brightness_changed()
        else:
            # Handle invalid input
            self.gain_spinbox.blockSignals(True)
            self.gain_spinbox.setValue(1.0)
            self.gain_spinbox.blockSignals(False)
            self.gain_slider.blockSignals(True)
            self.gain_slider.setValue(0)
            self.gain_slider.blockSignals(False)
            self._update_gain_label(1.0)
            self._save_current_params()
            self._emit_brightness_changed()

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
        self._emit_brightness_changed()  # This will call _sync_to_manager

    # ------------------------ label helpers ------------------------
    def _update_offset_label(self, value):
        if isinstance(value, (int, np.integer)):
            self.offset_value_label.setText(f"{value}")
        else:
            self.offset_value_label.setText(f"{value:.5f}")

    def _update_gain_label(self, value):
        if value < 0.01:
            self.gain_value_label.setText(f"{value:.6f}")
        elif value < 0.1:
            self.gain_value_label.setText(f"{value:.5f}")
        elif value >= 100:
            self.gain_value_label.setText(f"{value:.1f}")
        else:
            self.gain_value_label.setText(f"{value:.2f}")

    def _update_saturation_label(self, value):
        if isinstance(value, (int, np.integer)):
            self.saturation_value_label.setText(f"{value}")
        else:
            self.saturation_value_label.setText(f"{value:.5f}")

    # ------------------------ de-dup helpers ------------------------
    def _update_ranges_for_dtype(self, dtype_key):
        """Update is_float_type and ranges based on dtype key."""
        if dtype_key == "float":
            self.is_float_type = True
            self.offset_range = (-1.0, 1.0)
            self.saturation_range = (0.001, 10.0)
        elif dtype_key == "uint8":
            self.is_float_type = False
            self.offset_range = (-255, 255)
            self.saturation_range = (1, 255)
        elif dtype_key == "uint16":
            self.is_float_type = False
            self.offset_range = (-1023, 1023)
            self.saturation_range = (1, 4095)

    def _get_params_for_dtype(self, dtype_key):
        """Return (offset, gain, saturation) for dtype: saved if available, else defaults."""
        if dtype_key in self.dtype_params:
            return self.dtype_params[dtype_key]
        # Use dtype-specific defaults
        if dtype_key == "float":
            return (0.0, 1.0, 1.0)
        elif dtype_key == "uint8":
            return (0, 1.0, 255)
        elif dtype_key == "uint16":
            return (0, 1.0, 1023)
        else:
            return (0, 1.0, 255)

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
        """Configure gain slider/spinbox ranges; spinbox has extended range."""
        import math

        self.gain_slider.blockSignals(True)
        self.gain_slider.setRange(self._gain_log2_min, self._gain_log2_max)
        self.gain_slider.blockSignals(False)
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setRange(self._gain_spinbox_min, self._gain_spinbox_max)
        self.gain_spinbox.blockSignals(False)

    def _apply_values(self, offset, gain, saturation, clamp=True):
        import math

        if clamp:
            offset = max(self.offset_range[0], min(self.offset_range[1], offset))
            gain_for_spin = max(self._gain_spinbox_min, min(self._gain_spinbox_max, gain))
            # Round gain to nearest power of 2
            if gain_for_spin > 0:
                log2_val = math.log2(gain_for_spin)
                nearest_log2 = round(log2_val)
                nearest_log2 = max(self._gain_log2_min, min(self._gain_log2_max, nearest_log2))
                gain_for_spin = 2**nearest_log2
                gain_for_slider = nearest_log2
            else:
                gain_for_spin = 1.0
                gain_for_slider = 0
            sat = max(self.saturation_range[0], min(self.saturation_range[1], saturation))
        else:
            gain_for_spin = gain
            if gain > 0:
                gain_for_slider = round(math.log2(gain))
            else:
                gain_for_slider = 0
            sat = saturation

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
        self.gain_spinbox.setValue(gain_for_spin)
        self.gain_slider.setValue(int(gain_for_slider))
        self._update_gain_label(gain_for_spin)
        self.gain_slider.blockSignals(False)
        self.gain_spinbox.blockSignals(False)

        # Saturation
        self.saturation_slider.blockSignals(True)
        self.saturation_spinbox.blockSignals(True)
        self.saturation_spinbox.setValue(sat)
        self.saturation_slider.setValue(int(sat * 1000) if self.is_float_type else int(sat))
        self._update_saturation_label(sat)
        self.saturation_slider.blockSignals(False)
        self.saturation_spinbox.blockSignals(False)

        return offset, gain_for_spin, sat

    # ------------------------ state helpers ------------------------
    def _save_current_params(self):
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
                    # Convert dialog's dtype_key to a dummy dtype for manager's _dtype_key logic
                    # We can directly set _params_by_dtype since we know the keys
                    offset, gain, saturation = self.dtype_params.get(self.current_dtype, (0, 1.0, 255))
                    mgr._params_by_dtype[self.current_dtype] = (offset, gain, saturation)
        except Exception:
            pass

    def _load_params_for_dtype(self, dtype_key):
        """Load and apply saved params for dtype_key; no-op if not saved."""
        if dtype_key not in self.dtype_params:
            return
        offset, gain, saturation = self.dtype_params[dtype_key]
        self._update_ranges_for_dtype(dtype_key)
        self._configure_offset_widgets()
        self._configure_gain_widgets()
        self._configure_saturation_widgets()
        self._apply_values(offset, gain, saturation, clamp=True)

    # ------------------------ public API ------------------------
    def _emit_brightness_changed(self):
        offset = self.offset_spinbox.value()
        gain = self.gain_spinbox.value()
        saturation = self.saturation_spinbox.value()
        self.brightness_changed.emit(offset, gain, saturation)
        # Also save to manager's per-dtype storage using dialog's current_dtype
        self._sync_to_manager()

    def set_gain(self, gain_value):
        import math

        # Round to nearest power of 2
        if gain_value > 0:
            log2_value = math.log2(gain_value)
            nearest_log2 = round(log2_value)
            nearest_log2 = max(self._gain_log2_min, min(self._gain_log2_max, nearest_log2))
            clamped = 2**nearest_log2
        else:
            clamped = 1.0
            nearest_log2 = 0

        self.gain_slider.blockSignals(True)
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(clamped)
        self.gain_slider.setValue(nearest_log2)
        self._update_gain_label(clamped)
        self.gain_slider.blockSignals(False)
        self.gain_spinbox.blockSignals(False)
        self._save_current_params()
        self._emit_brightness_changed()

    def reset_parameters(self):
        self._reset_to_initial()
        self._save_current_params()
        self._emit_brightness_changed()

    def _reset_to_initial(self):
        import math

        self.offset_slider.blockSignals(True)
        self.offset_spinbox.blockSignals(True)
        self.offset_spinbox.setValue(self.initial_offset)
        self.offset_slider.setValue(int(self.initial_offset * 10))
        self._update_offset_label(self.initial_offset)
        self.offset_slider.blockSignals(False)
        self.offset_spinbox.blockSignals(False)

        self.gain_slider.blockSignals(True)
        self.gain_spinbox.blockSignals(True)
        # Round initial gain to nearest power of 2
        if self.initial_gain > 0:
            initial_log2 = round(math.log2(self.initial_gain))
            initial_log2 = max(self._gain_log2_min, min(self._gain_log2_max, initial_log2))
            rounded_gain = 2**initial_log2
        else:
            initial_log2 = 0
            rounded_gain = 1.0
        self.gain_spinbox.setValue(rounded_gain)
        self.gain_slider.setValue(initial_log2)
        self._update_gain_label(rounded_gain)
        self.gain_slider.blockSignals(False)
        self.gain_spinbox.blockSignals(False)

        self.saturation_slider.blockSignals(True)
        self.saturation_spinbox.blockSignals(True)
        self.saturation_spinbox.setValue(self.initial_saturation)
        self.saturation_slider.setValue(
            int(self.initial_saturation * 1000) if self.is_float_type else int(self.initial_saturation)
        )
        self._update_saturation_label(self.initial_saturation)
        self.saturation_slider.blockSignals(False)
        self.saturation_spinbox.blockSignals(False)

        self.dtype_params[self.current_dtype] = (
            self.initial_offset,
            rounded_gain,
            self.initial_saturation,
        )

    def get_parameters(self):
        return (
            self.offset_spinbox.value(),
            self.gain_spinbox.value(),
            self.saturation_spinbox.value(),
        )

    def update_for_new_image(self, image_array=None, image_path=None, keep_settings=True):
        old_dtype = self.current_dtype
        old_params = (
            self.offset_spinbox.value(),
            self.gain_spinbox.value(),
            self.saturation_spinbox.value(),
        )
        self.image_array = image_array
        self.image_path = image_path
        old_is_float = self.is_float_type

        self._determine_initial_values()
        self._gain_slider_min, self._gain_slider_max = self.gain_range

        if keep_settings:
            self.dtype_params[old_dtype] = old_params

        if hasattr(self, "dtype_combo"):
            self.dtype_combo.blockSignals(True)
            self.dtype_combo.setCurrentText(self.current_dtype)
            self.dtype_combo.blockSignals(False)

        if old_is_float != self.is_float_type:
            pass

        if keep_settings:
            if self.current_dtype in self.dtype_params:
                new_offset, new_gain, new_saturation = self.dtype_params[self.current_dtype]
            else:
                new_offset, new_gain, new_saturation = (
                    self.initial_offset,
                    self.initial_gain,
                    self.initial_saturation,
                )
        else:
            new_offset, new_gain, new_saturation = (
                self.initial_offset,
                self.initial_gain,
                self.initial_saturation,
            )

        self._configure_offset_widgets()
        self._configure_gain_widgets()
        self._configure_saturation_widgets()

        clamped_offset, clamped_gain, clamped_sat = self._apply_values(new_offset, new_gain, new_saturation, clamp=True)

        self.dtype_params[self.current_dtype] = (clamped_offset, clamped_gain, clamped_sat)
        self._emit_brightness_changed()

        if not keep_settings:
            self._reset_to_initial()
            self._emit_brightness_changed()

    # key handling remains in the dialog layer to integrate with parent actions
