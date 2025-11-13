"""Brightness adjustment dialog for tiling comparison."""

from typing import Dict
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QDoubleSpinBox,
    QPushButton,
    QGroupBox,
    QCheckBox,
)
from PySide6.QtCore import Signal

from PixelScopeViewer.ui.dialogs.display.tabs.logic import get_dtype_defaults


class TilingBrightnessDialog(QDialog):
    """Dialog for adjusting brightness parameters in tiling comparison.

    Provides per-dtype-group controls for offset and saturation,
    and a common gain control.
    """

    # Signal emitted when brightness parameters change
    brightness_changed = Signal(dict)  # Emits brightness_params_by_dtype dict

    def __init__(self, parent, brightness_params_by_dtype: Dict[str, Dict[str, float]], common_gain: float):
        """Initialize brightness dialog.

        Args:
            parent: Parent widget
            brightness_params_by_dtype: Dict mapping dtype groups to {offset, saturation}
            common_gain: Common gain value
        """
        super().__init__(parent)
        self.setWindowTitle("輝度調整 - タイリング比較")
        self.resize(400, 500)

        self.brightness_params_by_dtype = brightness_params_by_dtype.copy()
        self.common_gain = common_gain

        self._build_ui()
        self._update_values_from_params()

    def _build_ui(self):
        """Build the user interface."""
        layout = QVBoxLayout(self)

        # Common gain control
        gain_group = QGroupBox("共通ゲイン")
        gain_layout = QVBoxLayout(gain_group)

        gain_control_layout = QHBoxLayout()
        gain_control_layout.addWidget(QLabel("Gain:"))

        self.gain_spinbox = QDoubleSpinBox()
        self.gain_spinbox.setRange(0.0078125, 1024.0)  # 2^-7 to 2^10
        self.gain_spinbox.setDecimals(6)
        self.gain_spinbox.setSingleStep(0.01)
        self.gain_spinbox.setValue(self.common_gain)
        self.gain_spinbox.valueChanged.connect(self._on_gain_spinbox_changed)
        gain_control_layout.addWidget(self.gain_spinbox)

        gain_layout.addLayout(gain_control_layout)
        layout.addWidget(gain_group)

        # Per-dtype group controls
        self.dtype_controls = {}

        for dtype_group in sorted(self.brightness_params_by_dtype.keys()):
            group_box = QGroupBox(f"{dtype_group} パラメータ")
            group_layout = QVBoxLayout(group_box)

            # Get ranges from centralized defaults
            defaults = get_dtype_defaults(dtype_group)
            offset_range = defaults["offset_range"]
            sat_range = defaults["saturation_range"]
            is_float = defaults["is_float_type"]
            decimals = 5 if is_float else 0

            # Offset control
            offset_layout = QHBoxLayout()
            offset_layout.addWidget(QLabel("Offset:"))

            offset_spinbox = QDoubleSpinBox()
            offset_spinbox.setRange(offset_range[0], offset_range[1])
            offset_spinbox.setDecimals(decimals)
            offset_spinbox.setSingleStep(0.01 if is_float else 1.0)
            offset_spinbox.setValue(0.0)
            offset_spinbox.valueChanged.connect(lambda v, dg=dtype_group: self._on_offset_spinbox_changed(dg, v))
            offset_layout.addWidget(offset_spinbox)

            group_layout.addLayout(offset_layout)

            # Saturation control
            sat_layout = QHBoxLayout()
            sat_layout.addWidget(QLabel("Saturation:"))

            sat_spinbox = QDoubleSpinBox()
            sat_spinbox.setRange(sat_range[0], sat_range[1])
            sat_spinbox.setDecimals(decimals)
            sat_spinbox.setSingleStep(0.01 if is_float else 1.0)
            sat_spinbox.setValue(defaults["initial_saturation"])
            sat_spinbox.valueChanged.connect(lambda v, dg=dtype_group: self._on_saturation_spinbox_changed(dg, v))
            sat_layout.addWidget(sat_spinbox)

            group_layout.addLayout(sat_layout)

            layout.addWidget(group_box)

            # Store controls for later updates
            self.dtype_controls[dtype_group] = {
                "offset_spinbox": offset_spinbox,
                "sat_spinbox": sat_spinbox,
            }

        # Auto-apply checkbox
        self.auto_apply_checkbox = QCheckBox("自動適用")
        self.auto_apply_checkbox.setChecked(True)
        layout.addWidget(self.auto_apply_checkbox)

        # Button layout
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        reset_btn = QPushButton("リセット")
        reset_btn.clicked.connect(self._on_reset)
        btn_layout.addWidget(reset_btn)

        apply_btn = QPushButton("適用")
        apply_btn.clicked.connect(self._on_apply)
        btn_layout.addWidget(apply_btn)

        close_btn = QPushButton("閉じる")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def _update_values_from_params(self):
        """Update UI controls from current parameters."""
        # Update gain
        self.gain_spinbox.blockSignals(True)
        self.gain_spinbox.setValue(self.common_gain)
        self.gain_spinbox.blockSignals(False)

        # Update dtype-specific params
        for dtype_group, controls in self.dtype_controls.items():
            params = self.brightness_params_by_dtype[dtype_group]

            offset = params["offset"]
            saturation = params["saturation"]

            controls["offset_spinbox"].blockSignals(True)
            controls["sat_spinbox"].blockSignals(True)

            controls["offset_spinbox"].setValue(offset)
            controls["sat_spinbox"].setValue(saturation)

            controls["offset_spinbox"].blockSignals(False)
            controls["sat_spinbox"].blockSignals(False)

    def _on_gain_spinbox_changed(self, value: float):
        """Handle gain spinbox change."""
        self.common_gain = value

        if self.auto_apply_checkbox.isChecked():
            self._emit_brightness_changed()

    def _on_offset_spinbox_changed(self, dtype_group: str, value: float):
        """Handle offset spinbox change."""
        self.brightness_params_by_dtype[dtype_group]["offset"] = value

        if self.auto_apply_checkbox.isChecked():
            self._emit_brightness_changed()

    def _on_saturation_spinbox_changed(self, dtype_group: str, value: float):
        """Handle saturation spinbox change."""
        self.brightness_params_by_dtype[dtype_group]["saturation"] = value

        if self.auto_apply_checkbox.isChecked():
            self._emit_brightness_changed()

    def _on_reset(self):
        """Reset all parameters to defaults."""
        self.common_gain = 1.0

        for dtype_group in self.brightness_params_by_dtype:
            # Get defaults from centralized function
            defaults = get_dtype_defaults(dtype_group)

            self.brightness_params_by_dtype[dtype_group] = {
                "offset": defaults["initial_offset"],
                "saturation": defaults["initial_saturation"],
            }

        self._update_values_from_params()
        self._emit_brightness_changed()

    def _on_apply(self):
        """Apply current parameters."""
        self._emit_brightness_changed()

    def _emit_brightness_changed(self):
        """Emit brightness changed signal."""
        # Construct full parameter dict
        full_params = {
            dtype_group: {
                "gain": self.common_gain,
                "offset": params["offset"],
                "saturation": params["saturation"],
            }
            for dtype_group, params in self.brightness_params_by_dtype.items()
        }

        self.brightness_changed.emit(full_params)

    def get_brightness_params(self) -> tuple[Dict[str, Dict[str, float]], float]:
        """Get current brightness parameters.

        Returns:
            Tuple of (brightness_params_by_dtype, common_gain)
        """
        return (self.brightness_params_by_dtype.copy(), self.common_gain)
