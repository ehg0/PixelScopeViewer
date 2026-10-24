"""複数画像比較の brightness 調整 dialog。"""

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
from PixelScopeViewer.ui.common import defaults
from PixelScopeViewer.ui.common.widgets import set_value_silently


class TilingBrightnessDialog(QDialog):
    """全 tile 共通の gain と、dtype group ごとの offset・upper level を調整する dialog。

    Args:
        parent: 親 widget。
        brightness_params_by_dtype: dtype group から {offset, upper_level} への dict。
        common_gain: 共通の gain。
    """

    # dtype group から {gain, offset, upper_level} への dict
    brightness_changed = Signal(dict)

    # 最小化からの復元時に元の位置へ戻すため保持する
    _position_before_minimize = None

    def __init__(self, parent, brightness_params_by_dtype: dict[str, dict[str, float]], common_gain: float):
        super().__init__(parent)
        self.setWindowTitle("複数画像比較 - 輝度調整")
        self.resize(*defaults.TILING_BRIGHTNESS_DIALOG_SIZE)

        # 最小化を許可し、最前面に固定しない
        flags = Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.brightness_params_by_dtype = brightness_params_by_dtype.copy()
        self.common_gain = common_gain

        self._build_ui()
        self._update_values_from_params()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        gain_group = QGroupBox("共通ゲイン")
        gain_layout = QVBoxLayout(gain_group)

        gain_control_layout = QHBoxLayout()
        gain_control_layout.addWidget(QLabel("Gain:"))

        self.gain_spinbox = QDoubleSpinBox()
        self.gain_spinbox.setRange(0.0078125, 1024.0)  # 2^-7 〜 2^10
        self.gain_spinbox.setDecimals(6)
        self.gain_spinbox.setSingleStep(0.01)
        self.gain_spinbox.setValue(self.common_gain)
        self.gain_spinbox.valueChanged.connect(self._on_gain_spinbox_changed)
        gain_control_layout.addWidget(self.gain_spinbox)

        gain_layout.addLayout(gain_control_layout)
        layout.addWidget(gain_group)

        # dtype group ごとの offset と upper level
        self.dtype_controls = {}

        for dtype_group in sorted(self.brightness_params_by_dtype.keys()):
            group_box = QGroupBox(f"{dtype_group} パラメータ")
            group_layout = QVBoxLayout(group_box)

            defaults = get_dtype_defaults(dtype_group)
            offset_range = defaults["offset_range"]
            upper_level_range = defaults["upper_level_range"]
            is_float = defaults["is_float_type"]
            decimals = 5 if is_float else 0

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

            self.dtype_controls[dtype_group] = {
                "offset_spinbox": offset_spinbox,
                "upper_level_spinbox": upper_level_spinbox,
            }

        self.auto_apply_checkbox = QCheckBox("自動適用")
        self.auto_apply_checkbox.setChecked(True)
        layout.addWidget(self.auto_apply_checkbox)

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
        """現在の parameter を widget に反映する。"""
        set_value_silently(self.gain_spinbox, self.common_gain)

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
        self.common_gain = value

        if self.auto_apply_checkbox.isChecked():
            self._emit_brightness_changed()

    def _on_offset_spinbox_changed(self, dtype_group: str, value: float):
        self.brightness_params_by_dtype[dtype_group]["offset"] = value

        if self.auto_apply_checkbox.isChecked():
            self._emit_brightness_changed()

    def _on_upper_level_spinbox_changed(self, dtype_group: str, value: float):
        self.brightness_params_by_dtype[dtype_group]["upper_level"] = value

        if self.auto_apply_checkbox.isChecked():
            self._emit_brightness_changed()

    def _on_reset(self):
        """全 parameter を初期値に戻す。"""
        self.common_gain = 1.0

        for dtype_group in self.brightness_params_by_dtype:
            defaults = get_dtype_defaults(dtype_group)

            self.brightness_params_by_dtype[dtype_group] = {
                "offset": defaults["initial_offset"],
                "upper_level": defaults["initial_upper_level"],
            }

        self._update_values_from_params()
        self._emit_brightness_changed()

    def _on_apply(self):
        self._emit_brightness_changed()

    def _emit_brightness_changed(self):
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
        """(dtype group ごとの parameter, 共通の gain) を返す。"""
        return (self.brightness_params_by_dtype.copy(), self.common_gain)

    def changeEvent(self, event):
        # 最小化前の位置を保存し、復元時に戻す
        if event.type() == QEvent.WindowStateChange:
            if self.isMinimized():
                TilingBrightnessDialog._position_before_minimize = self.pos()
            elif event.oldState() & Qt.WindowMinimized and TilingBrightnessDialog._position_before_minimize is not None:
                self.move(TilingBrightnessDialog._position_before_minimize)
        super().changeEvent(event)
