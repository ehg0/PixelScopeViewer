"""Brightness adjustment dialog for controlling display intensity.

This module provides a dialog for adjusting image display brightness with:
- Offset: Shifts intensity baseline (can be negative)
- Gain: Amplifies intensity changes (positive only)
- Saturation: Sets the maximum intensity reference (positive only)

Formula: yout = gain * (yin - offset) / saturation * 255

The dialog adapts to image data type and provides both sliders and spinboxes
for precise control.
"""

import os
import numpy as np
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QDoubleSpinBox,
    QPushButton,
    QGroupBox,
)
from PySide6.QtCore import Qt, Signal


class BrightnessDialog(QDialog):
    """Dialog for adjusting display brightness parameters.

    Signals:
        brightness_changed: Emitted when any parameter changes (offset, gain, saturation)

    The dialog automatically detects image data type and sets appropriate
    parameter ranges and initial values.
    """

    brightness_changed = Signal(float, float, float)  # offset, gain, saturation

    def __init__(self, parent=None, image_array=None, image_path=None):
        """Initialize brightness adjustment dialog.

        Args:
            parent: Parent widget
            image_array: NumPy array of current image
            image_path: Path to current image file
        """
        super().__init__(parent)
        self.setWindowTitle("表示輝度調整")
        self.resize(450, 420)  # Optimized for new design
        self.setStyleSheet("QDialog { background-color: #fafafa; }")

        self.image_array = image_array
        self.image_path = image_path

        # Determine initial values based on image type
        self._determine_initial_values()

        # Extended ranges for controls
        self._gain_slider_min, self._gain_slider_max = self.gain_range
        self._gain_spinbox_min = 2**-7  # Allow down to 1/128 when bit shifting left
        self._gain_spinbox_max = 1024.0  # Allow up to 1024x when bit shifting right

        # Build UI
        self._build_ui()

        # Set initial values
        self._reset_to_initial()

    def _determine_initial_values(self):
        """Determine initial parameter values based on image data type and file extension."""
        # Default values
        self.initial_offset = 0
        self.initial_gain = 1.0
        self.initial_saturation = 255

        self.is_float_type = False
        self.offset_range = (-255, 255)
        self.gain_range = (0.1, 10.0)  # Gain should not be 0
        self.saturation_range = (1, 255)

        # Check file extension for .bin files
        if self.image_path and self.image_path.lower().endswith(".bin"):
            self.initial_saturation = 1023
            self.saturation_range = (1, 4095)
            self.offset_range = (-1023, 1023)

        # Check data type if array is available
        if self.image_array is not None:
            dtype = self.image_array.dtype

            if np.issubdtype(dtype, np.floating):
                # Float data type
                self.is_float_type = True
                self.initial_saturation = 1.0
                self.saturation_range = (0.001, 10.0)
                self.offset_range = (-1.0, 1.0)
                self.gain_range = (0.1, 10.0)  # Gain should not be 0
            elif np.issubdtype(dtype, np.integer):
                # Integer data type - check bit depth
                info = np.iinfo(dtype)
                max_val = info.max

                if max_val > 255:
                    # High bit depth (e.g., 10-bit, 12-bit, 16-bit)
                    self.initial_saturation = min(max_val, 4095)
                    self.saturation_range = (1, max_val)
                    self.offset_range = (-max_val // 2, max_val // 2)

    def _build_ui(self):
        """Build the dialog UI with sliders and spinboxes."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(25, 25, 25, 25)

        # Offset control
        # Offset label with value
        offset_label_layout = QHBoxLayout()
        offset_title_label = QLabel("オフセット (Offset)")
        offset_title_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        self.offset_value_label = QLabel(
            f"{self.initial_offset:.0f}" if not self.is_float_type else f"{self.initial_offset:.3f}"
        )
        self.offset_value_label.setStyleSheet("color: #555; font-size: 10pt;")
        offset_label_layout.addWidget(offset_title_label)
        offset_label_layout.addWidget(self.offset_value_label)
        offset_label_layout.addStretch()
        main_layout.addLayout(offset_label_layout)

        # Offset controls (caption + slider + spinbox)
        offset_control_layout = QHBoxLayout()
        offset_control_layout.setSpacing(10)

        # Offset caption label
        offset_caption = QLabel("Offset")
        offset_caption.setStyleSheet("font-size: 9pt; color: #888; min-width: 50px;")
        offset_caption.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        offset_control_layout.addWidget(offset_caption)

        self.offset_slider = QSlider(Qt.Horizontal)
        self.offset_slider.setRange(int(self.offset_range[0] * 10), int(self.offset_range[1] * 10))
        self.offset_slider.setTickPosition(QSlider.TicksBelow)
        self.offset_slider.setTickInterval((self.offset_range[1] - self.offset_range[0]) // 4)  # 5 major ticks
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

        if self.is_float_type:
            self.offset_spinbox = QDoubleSpinBox()
            self.offset_spinbox.setDecimals(3)
            self.offset_spinbox.setSingleStep(0.001)
            self.offset_spinbox.setReadOnly(False)
            self.offset_spinbox.setKeyboardTracking(False)
        else:
            self.offset_spinbox = QSpinBox()
            self.offset_spinbox.setSingleStep(1)
            self.offset_spinbox.setReadOnly(False)
            self.offset_spinbox.setKeyboardTracking(False)

        self.offset_spinbox.setRange(self.offset_range[0], self.offset_range[1])
        self.offset_spinbox.setStyleSheet("QSpinBox, QDoubleSpinBox { padding: 5px; font-size: 10pt; }")
        self.offset_spinbox.blockSignals(True)
        self.offset_spinbox.setValue(self.initial_offset)
        self.offset_spinbox.blockSignals(False)
        self.offset_spinbox.valueChanged.connect(self._on_offset_spinbox_changed)

        offset_control_layout.addWidget(self.offset_slider, 4)
        offset_control_layout.addWidget(self.offset_spinbox, 1)
        main_layout.addLayout(offset_control_layout)

        # Gain control
        # Gain label with value
        gain_label_layout = QHBoxLayout()
        gain_title_label = QLabel("ゲイン (Gain)")
        gain_title_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        gain_title_label.setToolTip("左ビットシフト : <,  右ビットシフト : >")

        self.gain_value_label = QLabel(f"{self.initial_gain:.2f}")
        self.gain_value_label.setStyleSheet("color: #555; font-size: 10pt;")
        gain_label_layout.addWidget(gain_title_label)
        gain_label_layout.addWidget(self.gain_value_label)
        gain_label_layout.addStretch()
        main_layout.addLayout(gain_label_layout)

        # Gain controls (caption + slider + spinbox)
        gain_control_layout = QHBoxLayout()

        gain_caption = QLabel("Gain")
        gain_caption.setStyleSheet("font-size: 9pt; color: #888; min-width: 50px;")
        gain_caption.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        gain_control_layout.addWidget(gain_caption)

        self.gain_slider = QSlider(Qt.Horizontal)
        self.gain_slider.setRange(int(self.gain_range[0] * 100), int(self.gain_range[1] * 100))
        self.gain_slider.setTickPosition(QSlider.TicksBelow)
        self.gain_slider.setTickInterval(int((self.gain_range[1] - self.gain_range[0]) * 100 / 4))  # 5 major ticks
        self.gain_slider.setStyleSheet(
            """
            QSlider::groove:horizontal { background: #ddd; height: 6px; border-radius: 3px; }
            QSlider::handle:horizontal { background: #666; width: 16px; margin: -5px 0; border-radius: 8px; }
            QSlider::handle:horizontal:hover { background: #444; }
        """
        )
        self.gain_slider.blockSignals(True)
        self.gain_slider.setValue(int(self.initial_gain * 100))
        self.gain_slider.blockSignals(False)
        self.gain_slider.valueChanged.connect(self._on_gain_slider_changed)

        self.gain_spinbox = QDoubleSpinBox()
        self.gain_spinbox.setDecimals(5)  # Support values like 0.0078125 (2^-7)
        self.gain_spinbox.setSingleStep(0.01)
        self.gain_spinbox.setReadOnly(False)
        self.gain_spinbox.setKeyboardTracking(False)
        # Spinbox range is wider than slider to accommodate bit shift operations
        # Left shift: 7 bits max for uint8 -> 2^-7 = 0.0078125
        # Right shift: 10 bits max -> 2^10 = 1024
        self.gain_spinbox.setRange(self._gain_spinbox_min, self._gain_spinbox_max)
        self.gain_spinbox.setStyleSheet("QDoubleSpinBox { padding: 5px; font-size: 10pt; }")
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(self.initial_gain)
        self.gain_spinbox.blockSignals(False)
        self.gain_spinbox.valueChanged.connect(self._on_gain_spinbox_changed)

        gain_control_layout.addWidget(self.gain_slider, 4)
        gain_control_layout.addWidget(self.gain_spinbox, 1)
        main_layout.addLayout(gain_control_layout)

        # Saturation control
        # Saturation label with value
        saturation_label_layout = QHBoxLayout()
        saturation_title_label = QLabel("飽和レベル (Saturation)")
        saturation_title_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        self.saturation_value_label = QLabel(
            f"{self.initial_saturation:.0f}" if not self.is_float_type else f"{self.initial_saturation:.3f}"
        )
        self.saturation_value_label.setStyleSheet("color: #555; font-size: 10pt;")
        saturation_label_layout.addWidget(saturation_title_label)
        saturation_label_layout.addWidget(self.saturation_value_label)
        saturation_label_layout.addStretch()
        main_layout.addLayout(saturation_label_layout)

        # Saturation controls (caption + slider + spinbox)
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
            self.saturation_spinbox = QDoubleSpinBox()
            self.saturation_spinbox.setDecimals(3)
            self.saturation_spinbox.setSingleStep(0.001)
            self.saturation_spinbox.setReadOnly(False)
            self.saturation_spinbox.setKeyboardTracking(False)
        else:
            self.saturation_slider.setRange(self.saturation_range[0], self.saturation_range[1])
            self.saturation_slider.setTickInterval((self.saturation_range[1] - self.saturation_range[0]) // 4)
            self.saturation_slider.blockSignals(True)
            self.saturation_slider.setValue(int(self.initial_saturation))
            self.saturation_slider.blockSignals(False)
            self.saturation_spinbox = QSpinBox()
            self.saturation_spinbox.setSingleStep(1)
            self.saturation_spinbox.setReadOnly(False)
            self.saturation_spinbox.setKeyboardTracking(False)

        self.saturation_slider.valueChanged.connect(self._on_saturation_slider_changed)
        self.saturation_spinbox.setRange(self.saturation_range[0], self.saturation_range[1])
        self.saturation_spinbox.setStyleSheet("QSpinBox, QDoubleSpinBox { padding: 5px; font-size: 10pt; }")
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

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)

        self.reset_button = QPushButton("Reset (Ctrl+R)")
        self.reset_button.clicked.connect(self._on_reset_clicked)
        button_layout.addWidget(self.reset_button)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)

        main_layout.addLayout(button_layout)

    def _on_offset_slider_changed(self, value):
        """Handle offset slider change."""
        actual_value = value / 10.0 if not self.is_float_type else value / 10.0
        self.offset_spinbox.blockSignals(True)
        self.offset_spinbox.setValue(actual_value)
        self.offset_spinbox.blockSignals(False)
        self._update_offset_label(actual_value)
        self._emit_brightness_changed()

    def _on_offset_spinbox_changed(self, value):
        """Handle offset spinbox change."""
        self.offset_slider.blockSignals(True)
        self.offset_slider.setValue(int(value * 10))
        self.offset_slider.blockSignals(False)
        self._update_offset_label(value)
        self._emit_brightness_changed()

    def _on_gain_slider_changed(self, value):
        """Handle gain slider change."""
        actual_value = value / 100.0
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(actual_value)
        self.gain_spinbox.blockSignals(False)
        self._update_gain_label(actual_value)
        self._emit_brightness_changed()

    def _on_gain_spinbox_changed(self, value):
        """Handle gain spinbox change."""
        self.gain_slider.blockSignals(True)
        # Only update slider if value is within slider range
        if self.gain_range[0] <= value <= self.gain_range[1]:
            self.gain_slider.setValue(int(value * 100))
        elif value < self.gain_range[0]:
            self.gain_slider.setValue(int(self.gain_range[0] * 100))
        else:
            self.gain_slider.setValue(int(self.gain_range[1] * 100))
        self.gain_slider.blockSignals(False)
        self._update_gain_label(value)
        self._emit_brightness_changed()

    def _on_saturation_slider_changed(self, value):
        """Handle saturation slider change."""
        if self.is_float_type:
            actual_value = value / 1000.0
        else:
            actual_value = value

        self.saturation_spinbox.blockSignals(True)
        self.saturation_spinbox.setValue(actual_value)
        self.saturation_spinbox.blockSignals(False)
        self._update_saturation_label(actual_value)
        self._emit_brightness_changed()

    def _on_saturation_spinbox_changed(self, value):
        """Handle saturation spinbox change."""
        self.saturation_slider.blockSignals(True)
        if self.is_float_type:
            self.saturation_slider.setValue(int(value * 1000))
        else:
            self.saturation_slider.setValue(int(value))
        self.saturation_slider.blockSignals(False)
        self._update_saturation_label(value)
        self._emit_brightness_changed()

    def _update_offset_label(self, value):
        """Update offset value label."""
        if isinstance(value, (int, np.integer)):
            self.offset_value_label.setText(f"{value}")
        else:
            self.offset_value_label.setText(f"{value:.2f}")

    def _update_gain_label(self, value):
        """Update gain value label."""
        # Use more decimal places for very small values, fewer for large values
        if value < 0.01:
            self.gain_value_label.setText(f"{value:.6f}")
        elif value < 0.1:
            self.gain_value_label.setText(f"{value:.5f}")
        elif value >= 100:
            self.gain_value_label.setText(f"{value:.1f}")
        else:
            self.gain_value_label.setText(f"{value:.2f}")

    def _update_saturation_label(self, value):
        """Update saturation value label."""
        if isinstance(value, (int, np.integer)):
            self.saturation_value_label.setText(f"{value}")
        else:
            self.saturation_value_label.setText(f"{value:.2f}")

    def _emit_brightness_changed(self):
        """Emit signal with current parameter values."""
        offset = self.offset_spinbox.value()
        gain = self.gain_spinbox.value()
        saturation = self.saturation_spinbox.value()
        self.brightness_changed.emit(offset, gain, saturation)

    def set_gain(self, gain_value):
        """Set gain value programmatically (e.g., from bit shift).

        Args:
            gain_value: New gain value to set
        """
        # Allow values outside slider range for bit shift operations.
        # Spinbox is clamped to an extended range while the slider stays within its UI bounds.
        self.gain_slider.blockSignals(True)
        self.gain_spinbox.blockSignals(True)

        # Update spinbox with clamping to extended range
        clamped_spinbox_value = max(self._gain_spinbox_min, min(self._gain_spinbox_max, gain_value))
        self.gain_spinbox.setValue(clamped_spinbox_value)

        # Update slider using its visual range
        if self._gain_slider_min <= gain_value <= self._gain_slider_max:
            self.gain_slider.setValue(int(gain_value * 100))
        else:
            # If outside slider range, set to nearest boundary
            if gain_value < self._gain_slider_min:
                self.gain_slider.setValue(int(self._gain_slider_min * 100))
            else:
                self.gain_slider.setValue(int(self._gain_slider_max * 100))

        self._update_gain_label(clamped_spinbox_value)

        self.gain_slider.blockSignals(False)
        self.gain_spinbox.blockSignals(False)

        self._emit_brightness_changed()

    def reset_parameters(self):
        """Reset parameters to their defaults and notify listeners."""
        self._reset_to_initial()
        self._emit_brightness_changed()

    def _on_reset_clicked(self):
        """Handle reset button click."""
        self.reset_parameters()

    def _reset_to_initial(self):
        """Reset all parameters to initial values."""
        self.offset_slider.blockSignals(True)
        self.offset_spinbox.blockSignals(True)
        self.offset_spinbox.setValue(self.initial_offset)
        self.offset_slider.setValue(int(self.initial_offset * 10))
        self._update_offset_label(self.initial_offset)
        self.offset_slider.blockSignals(False)
        self.offset_spinbox.blockSignals(False)

        self.gain_slider.blockSignals(True)
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(self.initial_gain)
        self.gain_slider.setValue(int(self.initial_gain * 100))
        self._update_gain_label(self.initial_gain)
        self.gain_slider.blockSignals(False)
        self.gain_spinbox.blockSignals(False)

        self.saturation_slider.blockSignals(True)
        self.saturation_spinbox.blockSignals(True)
        self.saturation_spinbox.setValue(self.initial_saturation)
        if self.is_float_type:
            self.saturation_slider.setValue(int(self.initial_saturation * 1000))
        else:
            self.saturation_slider.setValue(int(self.initial_saturation))
        self._update_saturation_label(self.initial_saturation)
        self.saturation_slider.blockSignals(False)
        self.saturation_spinbox.blockSignals(False)

    def get_parameters(self):
        """Get current brightness adjustment parameters.

        Returns:
            tuple: (offset, gain, saturation)
        """
        return (
            self.offset_spinbox.value(),
            self.gain_spinbox.value(),
            self.saturation_spinbox.value(),
        )

    def update_for_new_image(self, image_array=None, image_path=None, keep_settings=True):
        """Update dialog for a new image.

        Args:
            image_array: NumPy array of new image
            image_path: Path to new image file
            keep_settings: If True, keep current parameter values; if False, reset to defaults
        """
        # Store current values if we want to keep them
        if keep_settings:
            current_offset = self.offset_spinbox.value()
            current_gain = self.gain_spinbox.value()
            current_saturation = self.saturation_spinbox.value()

        self.image_array = image_array
        self.image_path = image_path

        # Store old float type state
        old_is_float_type = self.is_float_type

        # Determine new initial values
        self._determine_initial_values()
        self._gain_slider_min, self._gain_slider_max = self.gain_range

        # If data type changed, we need to recreate spinboxes
        if old_is_float_type != self.is_float_type:
            # For now, just update ranges - full recreation would be complex
            pass

        # Update ranges
        self.offset_slider.blockSignals(True)
        self.offset_slider.setRange(int(self.offset_range[0] * 10), int(self.offset_range[1] * 10))
        self.offset_slider.blockSignals(False)

        self.offset_spinbox.blockSignals(True)
        self.offset_spinbox.setRange(self.offset_range[0], self.offset_range[1])
        self.offset_spinbox.blockSignals(False)

        self.gain_slider.blockSignals(True)
        self.gain_slider.setRange(int(self.gain_range[0] * 100), int(self.gain_range[1] * 100))
        self.gain_slider.blockSignals(False)

        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setRange(self._gain_spinbox_min, self._gain_spinbox_max)
        self.gain_spinbox.blockSignals(False)

        self.saturation_slider.blockSignals(True)
        if self.is_float_type:
            self.saturation_slider.setRange(int(self.saturation_range[0] * 1000), int(self.saturation_range[1] * 1000))
        else:
            self.saturation_slider.setRange(self.saturation_range[0], self.saturation_range[1])
        self.saturation_slider.blockSignals(False)

        self.saturation_spinbox.blockSignals(True)
        self.saturation_spinbox.setRange(self.saturation_range[0], self.saturation_range[1])
        self.saturation_spinbox.blockSignals(False)

        if keep_settings:
            # Restore previous values (clamped to new ranges)
            self.offset_slider.blockSignals(True)
            self.offset_spinbox.blockSignals(True)

            # Clamp values to new ranges
            clamped_offset = max(self.offset_range[0], min(self.offset_range[1], current_offset))
            clamped_spinbox_gain = max(self._gain_spinbox_min, min(self._gain_spinbox_max, current_gain))
            clamped_slider_gain = max(self._gain_slider_min, min(self._gain_slider_max, current_gain))
            clamped_saturation = max(self.saturation_range[0], min(self.saturation_range[1], current_saturation))

            self.offset_spinbox.setValue(clamped_offset)
            self.offset_slider.setValue(int(clamped_offset * 10))
            self._update_offset_label(clamped_offset)
            self.offset_slider.blockSignals(False)
            self.offset_spinbox.blockSignals(False)

            self.gain_slider.blockSignals(True)
            self.gain_spinbox.blockSignals(True)
            self.gain_spinbox.setValue(clamped_spinbox_gain)
            self.gain_slider.setValue(int(clamped_slider_gain * 100))
            self._update_gain_label(clamped_spinbox_gain)
            self.gain_slider.blockSignals(False)
            self.gain_spinbox.blockSignals(False)

            self.saturation_slider.blockSignals(True)
            self.saturation_spinbox.blockSignals(True)
            self.saturation_spinbox.setValue(clamped_saturation)
            if self.is_float_type:
                self.saturation_slider.setValue(int(clamped_saturation * 1000))
            else:
                self.saturation_slider.setValue(int(clamped_saturation))
            self._update_saturation_label(clamped_saturation)
            self.saturation_slider.blockSignals(False)
            self.saturation_spinbox.blockSignals(False)

            # Emit signal with current (possibly clamped) values
            self._emit_brightness_changed()
        else:
            # Reset to initial values and emit signal
            self._reset_to_initial()
            self._emit_brightness_changed()

    def keyPressEvent(self, event):
        """Handle key press events.

        Forward < and > key events to parent window for bit shift operations.
        Also forward Ctrl+R for reset.
        """
        key = event.key()
        modifiers = event.modifiers()

        # Forward < and > keys to parent
        if key == Qt.Key_Less or key == Qt.Key_Comma:  # < key
            if self.parent():
                self.parent().left_bit_shift_action.trigger()
                event.accept()
                return
        elif key == Qt.Key_Greater or key == Qt.Key_Period:  # > key
            if self.parent():
                self.parent().right_bit_shift_action.trigger()
                event.accept()
                return
        elif key == Qt.Key_R and modifiers == Qt.ControlModifier:  # Ctrl+R
            if self.parent():
                self.parent().reset_brightness_action.trigger()
                event.accept()
                return

        # Call parent implementation for other keys
        super().keyPressEvent(event)
