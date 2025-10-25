"""Brightness and channel adjustment dialog for controlling display intensity and channel visibility.

This module provides a dialog for adjusting image display brightness with:
- Offset: Shifts intensity baseline (can be negative)
- Gain: Amplifies intensity changes (positive only)
- Saturation: Sets the maximum intensity reference (positive only)

Formula: yout = gain * (yin - offset) / saturation * 255

The dialog adapts to image data type and provides both sliders and spinboxes
for precise control. Also includes channel visibility selection.
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
    QTabWidget,
    QWidget,
    QCheckBox,
    QDialogButtonBox,
    QComboBox,
    QColorDialog,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap, QIcon


class BrightnessTab(QWidget):
    """Tab for adjusting display brightness parameters."""

    brightness_changed = Signal(float, float, float)  # offset, gain, saturation

    def __init__(self, parent=None, image_array=None, image_path=None):
        super().__init__(parent)
        self.image_array = image_array
        self.image_path = image_path

        # Storage for per-dtype parameters: {dtype_key: (offset, gain, saturation)}
        # Empty initially - will be populated as images are loaded
        self.dtype_params = {}
        self.current_dtype = "uint8"  # Will be updated by _determine_initial_values

        # Determine initial values based on image type
        self._determine_initial_values()

        # Extended ranges for controls
        self._gain_slider_min, self._gain_slider_max = self.gain_range
        self._gain_spinbox_min = 2**-7  # Allow down to 1/128 when bit shifting left
        self._gain_spinbox_max = 1024.0  # Allow up to 1024x when bit shifting right

        # Build UI
        self._build_ui()

        # Set initial values and save to dtype_params
        self._reset_to_initial()

    def _determine_initial_values(self):
        """Determine initial parameter values based on image data type and file extension."""
        # Default values
        self.current_dtype = "uint8"
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
                self.current_dtype = "float"
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
                    self.current_dtype = "uint16"
                    self.initial_saturation = min(max_val, 4095)
                    self.saturation_range = (1, max_val)
                    self.offset_range = (-max_val // 2, max_val // 2)

    def _build_ui(self):
        """Build the dialog UI with sliders and spinboxes."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(25, 25, 25, 25)

        # Data type selector
        dtype_layout = QHBoxLayout()
        dtype_label = QLabel("???? (Data Type):")
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

        # Offset control
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

        # Always use QDoubleSpinBox for offset (adjust decimals based on type)
        self.offset_spinbox = QDoubleSpinBox()
        if self.is_float_type:
            self.offset_spinbox.setDecimals(5)
            self.offset_spinbox.setSingleStep(0.01)
        else:
            self.offset_spinbox.setDecimals(0)
            self.offset_spinbox.setSingleStep(1)
        self.offset_spinbox.setReadOnly(False)
        self.offset_spinbox.setKeyboardTracking(True)  # Enable real-time tracking

        self.offset_spinbox.setRange(self.offset_range[0], self.offset_range[1])
        self.offset_spinbox.setStyleSheet("QSpinBox, QDoubleSpinBox { padding: 10px; font-size: 10pt; }")
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
        gain_title_label.setToolTip("ゲイン×0.5 : <,  ゲイン×2 : >")

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
        self.gain_spinbox.setDecimals(2)  # 小数点第2位まで表示
        self.gain_spinbox.setSingleStep(0.01)
        self.gain_spinbox.setReadOnly(False)
        self.gain_spinbox.setKeyboardTracking(True)  # Enable real-time tracking
        # Spinbox range is wider than slider to accommodate bit shift operations
        # Left shift: 7 bits max for uint8 -> 2^-7 = 0.0078125
        # Right shift: 10 bits max -> 2^10 = 1024
        self.gain_spinbox.setRange(self._gain_spinbox_min, self._gain_spinbox_max)
        self.gain_spinbox.setStyleSheet("QDoubleSpinBox { padding: 10px; font-size: 10pt; }")
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
            f"{self.initial_saturation:.0f}" if not self.is_float_type else f"{self.initial_saturation:.5f}"
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
        else:
            self.saturation_slider.setRange(self.saturation_range[0], self.saturation_range[1])
            self.saturation_slider.setTickInterval((self.saturation_range[1] - self.saturation_range[0]) // 4)
            self.saturation_slider.blockSignals(True)
            self.saturation_slider.setValue(int(self.initial_saturation))
            self.saturation_slider.blockSignals(False)

        # Always use QDoubleSpinBox for saturation (adjust decimals based on type)
        self.saturation_spinbox = QDoubleSpinBox()
        if self.is_float_type:
            self.saturation_spinbox.setDecimals(5)
            self.saturation_spinbox.setSingleStep(0.01)
        else:
            self.saturation_spinbox.setDecimals(0)
            self.saturation_spinbox.setSingleStep(1)
        self.saturation_spinbox.setReadOnly(False)
        self.saturation_spinbox.setKeyboardTracking(True)  # Enable real-time tracking

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

        # Reset button
        self.reset_button = QPushButton("Reset (Ctrl+R)")
        self.reset_button.clicked.connect(self._on_reset_clicked)
        main_layout.addWidget(self.reset_button)

        main_layout.addStretch()

    def _on_offset_slider_changed(self, value):
        """Handle offset slider change."""
        actual_value = value / 10.0 if not self.is_float_type else value / 10.0
        self.offset_spinbox.blockSignals(True)
        self.offset_spinbox.setValue(actual_value)
        self.offset_spinbox.blockSignals(False)
        self._update_offset_label(actual_value)
        self._save_current_params()
        self._emit_brightness_changed()

    def _on_offset_spinbox_changed(self, value):
        """Handle offset spinbox change."""
        self.offset_slider.blockSignals(True)
        self.offset_slider.setValue(int(value * 10))
        self.offset_slider.blockSignals(False)
        self._update_offset_label(value)
        self._save_current_params()
        self._emit_brightness_changed()

    def _on_gain_slider_changed(self, value):
        """Handle gain slider change."""
        actual_value = value / 100.0
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(actual_value)
        self.gain_spinbox.blockSignals(False)
        self._update_gain_label(actual_value)
        self._save_current_params()
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
        self._save_current_params()
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
        self._save_current_params()
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
        self._save_current_params()
        self._emit_brightness_changed()

    def _update_offset_label(self, value):
        """Update offset value label."""
        if isinstance(value, (int, np.integer)):
            self.offset_value_label.setText(f"{value}")
        else:
            self.offset_value_label.setText(f"{value:.5f}")

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
            self.saturation_value_label.setText(f"{value:.5f}")

    def _save_current_params(self):
        """Save current parameters to dtype_params dict."""
        current_params = (
            self.offset_spinbox.value(),
            self.gain_spinbox.value(),
            self.saturation_spinbox.value(),
        )
        self.dtype_params[self.current_dtype] = current_params

    def _load_params_for_dtype(self, dtype_key):
        """Load parameters for the specified dtype."""
        if dtype_key not in self.dtype_params:
            return

        offset, gain, saturation = self.dtype_params[dtype_key]

        # Update ranges based on dtype
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

        # Update slider/spinbox ranges
        self.offset_slider.blockSignals(True)
        self.offset_slider.setRange(int(self.offset_range[0] * 10), int(self.offset_range[1] * 10))
        self.offset_slider.blockSignals(False)

        self.offset_spinbox.blockSignals(True)
        self.offset_spinbox.setRange(self.offset_range[0], self.offset_range[1])
        # Update decimals and step for offset spinbox
        if self.is_float_type:
            self.offset_spinbox.setDecimals(5)
            self.offset_spinbox.setSingleStep(0.01)
        else:
            self.offset_spinbox.setDecimals(0)
            self.offset_spinbox.setSingleStep(1)
        self.offset_spinbox.blockSignals(False)

        if self.is_float_type:
            self.saturation_slider.blockSignals(True)
            self.saturation_slider.setRange(int(self.saturation_range[0] * 1000), int(self.saturation_range[1] * 1000))
            self.saturation_slider.blockSignals(False)
        else:
            self.saturation_slider.blockSignals(True)
            self.saturation_slider.setRange(self.saturation_range[0], self.saturation_range[1])
            self.saturation_slider.blockSignals(False)

        self.saturation_spinbox.blockSignals(True)
        self.saturation_spinbox.setRange(self.saturation_range[0], self.saturation_range[1])
        # Update decimals and step for saturation spinbox
        if self.is_float_type:
            self.saturation_spinbox.setDecimals(5)
            self.saturation_spinbox.setSingleStep(0.01)
        else:
            self.saturation_spinbox.setDecimals(0)
            self.saturation_spinbox.setSingleStep(1)
        self.saturation_spinbox.blockSignals(False)

        # Set values
        self.offset_spinbox.setValue(offset)
        self.offset_slider.setValue(int(offset * 10))
        self._update_offset_label(offset)

        self.gain_spinbox.setValue(gain)
        self.gain_slider.setValue(int(gain * 100))
        self._update_gain_label(gain)

        self.saturation_spinbox.setValue(saturation)
        if self.is_float_type:
            self.saturation_slider.setValue(int(saturation * 1000))
        else:
            self.saturation_slider.setValue(int(saturation))
        self._update_saturation_label(saturation)

    def _on_dtype_changed(self, dtype_key):
        """Handle dtype combo box selection change."""
        # Save current params before switching
        self._save_current_params()

        # Update current dtype
        self.current_dtype = dtype_key

        # Load params for new dtype
        self._load_params_for_dtype(dtype_key)

        # Emit change
        self._emit_brightness_changed()

    def _emit_brightness_changed(self):
        """Emit signal with current parameter values."""
        offset = self.offset_spinbox.value()
        gain = self.gain_spinbox.value()
        saturation = self.saturation_spinbox.value()

        self.brightness_changed.emit(offset, gain, saturation)

    def set_gain(self, gain_value):
        """プログラム的にゲイン値を設定します（例: ビットシフトによる更新）。"""
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

        self._save_current_params()
        self._emit_brightness_changed()

    def reset_parameters(self):
        """パラメータを初期値に戻し、変更をリスナに通知します。"""
        self._reset_to_initial()
        self._save_current_params()
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

        # Update dtype_params with the reset values
        self.dtype_params[self.current_dtype] = (self.initial_offset, self.initial_gain, self.initial_saturation)

    def get_parameters(self):
        """現在の輝度補正パラメータを取得します。"""
        return (
            self.offset_spinbox.value(),
            self.gain_spinbox.value(),
            self.saturation_spinbox.value(),
        )

    def update_for_new_image(self, image_array=None, image_path=None, keep_settings=True):
        """新しい画像に合わせてダイアログのパラメータ範囲／表示を更新します。"""
        # Save current parameters to old dtype BEFORE changing anything
        if keep_settings:
            old_dtype = self.current_dtype
            old_params = (
                self.offset_spinbox.value(),
                self.gain_spinbox.value(),
                self.saturation_spinbox.value(),
            )
            self.dtype_params[old_dtype] = old_params

        self.image_array = image_array
        self.image_path = image_path

        # Store old float type state
        old_is_float_type = self.is_float_type

        # Determine new initial values based on new image (this changes self.current_dtype)
        self._determine_initial_values()
        self._gain_slider_min, self._gain_slider_max = self.gain_range

        # Update dtype combo to match detected image dtype
        if hasattr(self, "dtype_combo"):
            self.dtype_combo.blockSignals(True)
            self.dtype_combo.setCurrentText(self.current_dtype)
            self.dtype_combo.blockSignals(False)

        # If data type changed, we need to recreate spinboxes
        if old_is_float_type != self.is_float_type:
            # For now, just update ranges - full recreation would be complex
            pass

        # Determine the values to use for the new dtype BEFORE updating ranges
        if keep_settings:
            if self.current_dtype in self.dtype_params:
                new_offset, new_gain, new_saturation = self.dtype_params[self.current_dtype]
            else:
                # New dtype not yet in params - use initial values from image detection
                new_offset, new_gain, new_saturation = self.initial_offset, self.initial_gain, self.initial_saturation
        else:
            # Use initial values when not keeping settings
            new_offset, new_gain, new_saturation = self.initial_offset, self.initial_gain, self.initial_saturation

        # Update ranges AND set values together with signals blocked
        self.offset_slider.blockSignals(True)
        self.offset_spinbox.blockSignals(True)
        self.offset_slider.setRange(int(self.offset_range[0] * 10), int(self.offset_range[1] * 10))
        self.offset_spinbox.setRange(self.offset_range[0], self.offset_range[1])
        # Update decimals and step for offset spinbox based on new dtype
        if self.is_float_type:
            self.offset_spinbox.setDecimals(5)
            self.offset_spinbox.setSingleStep(0.01)
        else:
            self.offset_spinbox.setDecimals(0)
            self.offset_spinbox.setSingleStep(1)
        # Clamp and set offset value
        clamped_offset = max(self.offset_range[0], min(self.offset_range[1], new_offset))
        self.offset_spinbox.setValue(clamped_offset)
        self.offset_slider.setValue(int(clamped_offset * 10))
        self._update_offset_label(clamped_offset)
        self.offset_slider.blockSignals(False)
        self.offset_spinbox.blockSignals(False)

        self.gain_slider.blockSignals(True)
        self.gain_spinbox.blockSignals(True)
        self.gain_slider.setRange(int(self.gain_range[0] * 100), int(self.gain_range[1] * 100))
        self.gain_spinbox.setRange(self._gain_spinbox_min, self._gain_spinbox_max)
        # Clamp and set gain value
        clamped_spinbox_gain = max(self._gain_spinbox_min, min(self._gain_spinbox_max, new_gain))
        clamped_slider_gain = max(self._gain_slider_min, min(self._gain_slider_max, new_gain))
        self.gain_spinbox.setValue(clamped_spinbox_gain)
        self.gain_slider.setValue(int(clamped_slider_gain * 100))
        self._update_gain_label(clamped_spinbox_gain)
        self.gain_slider.blockSignals(False)
        self.gain_spinbox.blockSignals(False)

        self.saturation_slider.blockSignals(True)
        self.saturation_spinbox.blockSignals(True)
        if self.is_float_type:
            self.saturation_slider.setRange(int(self.saturation_range[0] * 1000), int(self.saturation_range[1] * 1000))
        else:
            self.saturation_slider.setRange(self.saturation_range[0], self.saturation_range[1])
        self.saturation_spinbox.setRange(self.saturation_range[0], self.saturation_range[1])
        # Update decimals and step for saturation spinbox based on new dtype
        if self.is_float_type:
            self.saturation_spinbox.setDecimals(5)
            self.saturation_spinbox.setSingleStep(0.01)
        else:
            self.saturation_spinbox.setDecimals(0)
            self.saturation_spinbox.setSingleStep(1)
        # Clamp and set saturation value
        clamped_saturation = max(self.saturation_range[0], min(self.saturation_range[1], new_saturation))
        self.saturation_spinbox.setValue(clamped_saturation)
        if self.is_float_type:
            self.saturation_slider.setValue(int(clamped_saturation * 1000))
        else:
            self.saturation_slider.setValue(int(clamped_saturation))
        self._update_saturation_label(clamped_saturation)
        self.saturation_slider.blockSignals(False)
        self.saturation_spinbox.blockSignals(False)

        # Save the set values for the new dtype to ensure consistency
        self.dtype_params[self.current_dtype] = (clamped_offset, clamped_spinbox_gain, clamped_saturation)

        # Emit signal to apply the loaded settings to the new image
        # This is necessary even when keep_settings=True because the image has changed
        # and we need to apply the dtype-specific settings to it
        self._emit_brightness_changed()

        # Reset and emit for keep_settings=False case
        if not keep_settings:
            # Reset to initial values and emit signal again
            self._reset_to_initial()
            self._emit_brightness_changed()

    def keyPressEvent(self, event):
        """Handle key press events.

        Forward < and > key events to parent window for bit shift operations.
        Also forward Ctrl+R for reset.
        ESC key: Cancel spinbox editing without closing dialog.
        """
        key = event.key()
        modifiers = event.modifiers()

        # ESC key: Clear focus from spinbox (cancel editing) instead of closing dialog
        if key == Qt.Key_Escape:
            focused_widget = self.focusWidget()
            if focused_widget and isinstance(focused_widget, (QSpinBox, QDoubleSpinBox)):
                # Clear focus to finish editing without closing dialog
                focused_widget.clearFocus()
                event.accept()
                return
            # If not in spinbox editing, don't close dialog - just ignore
            event.ignore()
            return

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


class ChannelTab(QWidget):
    """Tab for selecting visible channels."""

    channels_changed = Signal(list)  # list of bools for channel visibility
    channel_colors_changed = Signal(list)  # list of colors for channels

    def __init__(self, parent=None, image_array=None, image_path=None, initial_channels=None, initial_colors=None):
        super().__init__(parent)
        self.image_array = image_array
        self.checkboxes = []
        self.color_buttons = []
        self.channel_colors = []

        self._setup_ui(initial_channels, initial_colors)

    def _setup_ui(self, initial_channels=None, initial_colors=None):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # Channel selection
        channel_group = QGroupBox("表示チャンネル (Visible Channels)")
        channel_layout = QVBoxLayout(channel_group)

        self.checkboxes = []
        self.color_buttons = []
        self.channel_colors = []

        if self.image_array is not None and self.image_array.ndim >= 3:
            n_channels = self.image_array.shape[2]

            # Set default colors for 3-channel images
            if n_channels == 3 and initial_colors is None:
                initial_colors = [QColor(255, 0, 0), QColor(0, 255, 0), QColor(0, 0, 255)]  # R, G, B
            elif initial_colors is None:
                initial_colors = [QColor(255, 255, 255)] * n_channels  # White for other channel counts

            for i in range(n_channels):
                # Create horizontal layout for each channel
                channel_row = QHBoxLayout()

                # Checkbox
                cb = QCheckBox(f"チャンネル {i} (Channel {i})")
                # Set checked state based on initial_channels
                if initial_channels and i < len(initial_channels):
                    cb.setChecked(initial_channels[i])
                else:
                    cb.setChecked(True)  # Default to checked
                cb.stateChanged.connect(self._on_channel_changed)
                self.checkboxes.append(cb)
                channel_row.addWidget(cb)

                # Color selection button
                color = initial_colors[i] if i < len(initial_colors) else QColor(255, 255, 255)
                self.channel_colors.append(color)

                color_button = QPushButton()
                color_button.setFixedSize(60, 24)
                color_button.setToolTip("クリックして色を選択 (Click to select color)")
                self._update_color_button(color_button, color)
                color_button.clicked.connect(lambda checked, idx=i: self._select_color(idx))
                self.color_buttons.append(color_button)
                channel_row.addWidget(color_button)

                channel_row.addStretch()
                channel_layout.addLayout(channel_row)
        else:
            label = QLabel("チャンネル選択なし (グレースケール画像)")
            label.setStyleSheet("color: #888;")
            channel_layout.addWidget(label)

        layout.addWidget(channel_group)

        # Select All / Deselect All buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        self.select_all_btn = QPushButton("すべて選択 (Select All)")
        self.select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("すべて解除 (Deselect All)")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        button_layout.addWidget(self.deselect_all_btn)

        layout.addLayout(button_layout)
        layout.addStretch()

    def _on_channel_changed(self):
        self._emit_change()

    def _select_color(self, channel_idx):
        """Open color picker dialog for the specified channel."""
        current_color = self.channel_colors[channel_idx]
        color = QColorDialog.getColor(current_color, self, f"チャンネル {channel_idx} の色を選択")

        if color.isValid():
            self.channel_colors[channel_idx] = color
            self._update_color_button(self.color_buttons[channel_idx], color)
            self._emit_color_change()

    def _update_color_button(self, button, color):
        """Update button appearance with the selected color."""
        # Create a colored icon
        pixmap = QPixmap(48, 16)
        pixmap.fill(color)
        button.setIcon(QIcon(pixmap))
        button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #999;")
        button.setText("")

    def _emit_change(self):
        states = [cb.isChecked() for cb in self.checkboxes]
        self.channels_changed.emit(states)

    def _emit_color_change(self):
        self.channel_colors_changed.emit(self.channel_colors)

    def select_all(self):
        for cb in self.checkboxes:
            cb.setChecked(True)

    def deselect_all(self):
        for cb in self.checkboxes:
            cb.setChecked(False)

    def get_channel_states(self):
        return [cb.isChecked() for cb in self.checkboxes]

    def set_channel_states(self, states):
        for i, state in enumerate(states):
            if i < len(self.checkboxes):
                self.checkboxes[i].setChecked(state)

    def get_channel_colors(self):
        return self.channel_colors.copy()

    def set_channel_colors(self, colors):
        for i, color in enumerate(colors):
            if i < len(self.channel_colors):
                self.channel_colors[i] = color
                if i < len(self.color_buttons):
                    self._update_color_button(self.color_buttons[i], color)

    def update_for_new_image(self, image_array=None, channel_checks=None, channel_colors=None):
        """Update channel selection for new image."""
        self.image_array = image_array

        # Get the channel group layout
        channel_group = self.findChild(QGroupBox, "表示チャンネル (Visible Channels)")
        if not channel_group:
            # If not found, try to find it in the layout
            for child in self.children():
                if isinstance(child, QGroupBox) and "チャンネル" in child.title():
                    channel_group = child
                    break

        if channel_group:
            channel_layout = channel_group.layout()

            # Clear existing checkboxes and color buttons
            for cb in self.checkboxes:
                cb.setParent(None)
                cb.deleteLater()
            self.checkboxes.clear()

            for button in self.color_buttons:
                button.setParent(None)
                button.deleteLater()
            self.color_buttons.clear()
            self.channel_colors.clear()

            # Clear layout
            while channel_layout.count():
                item = channel_layout.takeAt(0)
                widget = item.widget()
                if widget:
                    widget.setParent(None)
                    widget.deleteLater()
                elif item.layout():
                    # Clear sub-layout recursively
                    sub_layout = item.layout()
                    while sub_layout.count():
                        sub_item = sub_layout.takeAt(0)
                        sub_widget = sub_item.widget()
                        if sub_widget:
                            sub_widget.setParent(None)
                            sub_widget.deleteLater()
                    sub_layout.setParent(None)
                    sub_layout.deleteLater()

            # Rebuild channel selection
            if self.image_array is not None and self.image_array.ndim >= 3:
                n_channels = self.image_array.shape[2]

                # Set default colors for 3-channel images
                if n_channels == 3 and channel_colors is None:
                    channel_colors = [QColor(255, 0, 0), QColor(0, 255, 0), QColor(0, 0, 255)]  # R, G, B
                elif channel_colors is None:
                    channel_colors = [QColor(255, 255, 255)] * n_channels

                for i in range(n_channels):
                    # Create horizontal layout for each channel
                    channel_row = QHBoxLayout()

                    # Checkbox
                    cb = QCheckBox(f"チャンネル {i} (Channel {i})")
                    # Set checked state based on channel_checks
                    if channel_checks and i < len(channel_checks):
                        cb.setChecked(channel_checks[i])
                    else:
                        cb.setChecked(True)  # Default to checked
                    cb.stateChanged.connect(self._on_channel_changed)
                    self.checkboxes.append(cb)
                    channel_row.addWidget(cb)

                    # Color selection button
                    color = channel_colors[i] if i < len(channel_colors) else QColor(255, 255, 255)
                    self.channel_colors.append(color)

                    color_button = QPushButton()
                    color_button.setFixedSize(60, 24)
                    color_button.setToolTip("クリックして色を選択 (Click to select color)")
                    self._update_color_button(color_button, color)
                    color_button.clicked.connect(lambda checked, idx=i: self._select_color(idx))
                    self.color_buttons.append(color_button)
                    channel_row.addWidget(color_button)

                    channel_row.addStretch()
                    channel_layout.addLayout(channel_row)
            else:
                label = QLabel("チャンネル選択なし (グレースケール画像)")
                label.setStyleSheet("color: #888;")
                channel_layout.addWidget(label)


class BrightnessDialog(QDialog):
    """Dialog for adjusting display brightness parameters and channel visibility.

    Signals:
        brightness_changed: Emitted when brightness parameters change (offset, gain, saturation)
        channels_changed: Emitted when channel visibility changes

    The dialog automatically detects image data type and sets appropriate
    parameter ranges and initial values.
    """

    brightness_changed = Signal(float, float, float)  # offset, gain, saturation
    channels_changed = Signal(list)  # list of bools for channel visibility
    channel_colors_changed = Signal(list)  # list of colors for channels

    # Persist window geometry across openings so it doesn't jump based on cursor/OS heuristics
    _saved_geometry = None

    def __init__(
        self,
        parent=None,
        image_array=None,
        image_path=None,
        initial_brightness=(0.0, 1.0, 255.0),
        initial_channels=None,
        initial_colors=None,
    ):
        """Initialize brightness and channel adjustment dialog.

        Args:
            parent: Parent widget
            image_array: NumPy array of current image
            image_path: Path to current image file
            initial_brightness: Tuple of (offset, gain, saturation)
            initial_channels: List of bools for channel visibility
            initial_colors: List of QColor objects for channel colors
        """
        super().__init__(parent)
        self.setWindowTitle("表示設定 (Display Settings)")
        self.resize(500, 600)
        self.setStyleSheet("QDialog { background-color: #fafafa; }")

        self.image_array = image_array
        self.image_path = image_path

        # Create tab widget
        self.tabs = QTabWidget()

        # Brightness tab
        self.brightness_tab = BrightnessTab(self, image_array, image_path)
        self.tabs.addTab(self.brightness_tab, "輝度調整 (Brightness)")

        # Channel tab
        self.channel_tab = ChannelTab(self, image_array, image_path, initial_channels, initial_colors)
        self.tabs.addTab(self.channel_tab, "チャンネル (Channels)")

        # Connect signals
        self.brightness_tab.brightness_changed.connect(self.brightness_changed)
        self.channel_tab.channels_changed.connect(self.channels_changed)
        self.channel_tab.channel_colors_changed.connect(self.channel_colors_changed)

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

        # Note: OK/Cancel buttons are intentionally omitted for a modeless, live-updating dialog

        # Restore last window geometry if available to avoid cursor-dependent positioning
        try:
            if BrightnessDialog._saved_geometry:
                self.restoreGeometry(BrightnessDialog._saved_geometry)
        except Exception:
            pass

        # Set initial values
        if initial_brightness:
            self.set_brightness(*initial_brightness)
        if initial_channels:
            self.set_channels(initial_channels)
        if initial_colors:
            self.set_channel_colors(initial_colors)

    def set_brightness(self, offset, gain, saturation):
        """Set brightness parameters."""
        self.brightness_tab.offset_spinbox.setValue(offset)
        self.brightness_tab.gain_spinbox.setValue(gain)
        self.brightness_tab.saturation_spinbox.setValue(saturation)

    def set_gain(self, gain_value: float):
        """Programmatically set gain value via the Brightness tab.

        This provides a stable API for parent viewer code to adjust the gain
        (e.g., when handling keyboard shortcuts like '<' and '>').
        """
        try:
            if hasattr(self, "brightness_tab") and hasattr(self.brightness_tab, "set_gain"):
                self.brightness_tab.set_gain(gain_value)
        except Exception:
            # Fail silently to avoid interrupting UI flow
            pass

    def reset_parameters(self):
        """Reset parameters via the Brightness tab and emit change.

        Wrapper to keep viewer code simple regardless of internal tab structure.
        """
        try:
            if hasattr(self, "brightness_tab") and hasattr(self.brightness_tab, "reset_parameters"):
                self.brightness_tab.reset_parameters()
        except Exception:
            pass

    def set_channels(self, channels):
        """Set channel visibility."""
        self.channel_tab.set_channel_states(channels)

    def get_brightness(self):
        """Get current brightness parameters."""
        return self.brightness_tab.get_parameters()

    def get_channels(self):
        """Get current channel visibility."""
        return self.channel_tab.get_channel_states()

    def get_channel_colors(self):
        """Get current channel colors."""
        return self.channel_tab.get_channel_colors()

    def set_channel_colors(self, colors):
        """Set channel colors."""
        self.channel_tab.set_channel_colors(colors)

    def update_for_new_image(
        self, image_array=None, image_path=None, keep_settings=True, channel_checks=None, channel_colors=None
    ):
        """Update dialog for new image."""
        self.image_array = image_array
        self.image_path = image_path
        self.brightness_tab.update_for_new_image(image_array, image_path, keep_settings)
        self.channel_tab.update_for_new_image(image_array, channel_checks, channel_colors)

    def moveEvent(self, event):
        # Save geometry whenever the dialog is moved
        try:
            BrightnessDialog._saved_geometry = self.saveGeometry()
        except Exception:
            pass
        super().moveEvent(event)

    def resizeEvent(self, event):
        # Save geometry whenever the dialog is resized
        try:
            BrightnessDialog._saved_geometry = self.saveGeometry()
        except Exception:
            pass
        super().resizeEvent(event)

    def keyPressEvent(self, event):
        """Override ESC key to prevent closing dialog."""
        if event.key() == Qt.Key_Escape:
            # Don't close dialog on ESC, just ignore the event
            event.ignore()
            return
        super().keyPressEvent(event)
