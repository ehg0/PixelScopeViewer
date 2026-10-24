"""Brightness adjustment dialog for tiling comparison."""

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from PixelScopeViewer.core.constants import get_dtype_defaults


class TilingBrightnessDialog(QDialog):
    """Dialog for adjusting brightness parameters in tiling comparison.

    Provides per-dtype-group controls for offset and upper_level,
    and a common gain control.
    """

    # Signal emitted when brightness parameters change
    brightness_changed = Signal(dict)  # Emits brightness_params_by_dtype dict

    # Store position before minimize to restore after showNormal()
    _position_before_minimize = None

    def __init__(self, parent, brightness_params_by_dtype: dict[str, dict[str, float]], common_gain: float):
        """Initialize brightness dialog.

        Args:
            parent: Parent widget
            brightness_params_by_dtype: Dict mapping dtype groups to {offset, upper_level}
            common_gain: Common gain value
        """
        super().__init__(parent)
        self.setWindowTitle("複数画像比較 - 輝度調整")
        self.resize(400, 500)

        # Set window flags to allow minimizing and prevent staying on top
        flags = Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_DeleteOnClose)

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
            upper_level_range = defaults["upper_level_range"]
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

            # Upper_level control
            upper_level_layout = QHBoxLayout()
            upper_level_layout.addWidget(QLabel("Upper_level:"))

            upper_level_spinbox = QDoubleSpinBox()
            upper_level_spinbox.setRange(upper_level_range[0], upper_level_range[1])
            upper_level_spinbox.setDecimals(decimals)
            upper_level_spinbox.setSingleStep(0.01 if is_float else 1.0)
            upper_level_spinbox.setValue(defaults["initial_upper_level"])
            upper_level_spinbox.valueChanged.connect(
                lambda v, dg=dtype_group: self._on_upper_level_spinbox_changed(dg, v)
            )
            upper_level_layout.addWidget(upper_level_spinbox)

            group_layout.addLayout(upper_level_layout)

            layout.addWidget(group_box)

            # Store controls for later updates
            self.dtype_controls[dtype_group] = {
                "offset_spinbox": offset_spinbox,
                "upper_level_spinbox": upper_level_spinbox,
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
            upper_level = params["upper_level"]

            controls["offset_spinbox"].blockSignals(True)
            controls["upper_level_spinbox"].blockSignals(True)

            controls["offset_spinbox"].setValue(offset)
            controls["upper_level_spinbox"].setValue(upper_level)

            controls["offset_spinbox"].blockSignals(False)
            controls["upper_level_spinbox"].blockSignals(False)

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

    def _on_upper_level_spinbox_changed(self, dtype_group: str, value: float):
        """Handle upper_level spinbox change."""
        self.brightness_params_by_dtype[dtype_group]["upper_level"] = value

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
                "upper_level": defaults["initial_upper_level"],
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
                "upper_level": params["upper_level"],
            }
            for dtype_group, params in self.brightness_params_by_dtype.items()
        }

        self.brightness_changed.emit(full_params)

    def get_brightness_params(self) -> tuple[dict[str, dict[str, float]], float]:
        """Get current brightness parameters.

        Returns:
            Tuple of (brightness_params_by_dtype, common_gain)
        """
        return (self.brightness_params_by_dtype.copy(), self.common_gain)

    def changeEvent(self, event):
        """Handle window state changes to preserve position during minimize/restore."""
        if event.type() == QEvent.WindowStateChange:
            if self.isMinimized():
                # Save current position before minimize
                TilingBrightnessDialog._position_before_minimize = self.pos()
            elif event.oldState() & Qt.WindowMinimized and TilingBrightnessDialog._position_before_minimize is not None:
                self.move(TilingBrightnessDialog._position_before_minimize)
        super().changeEvent(event)
