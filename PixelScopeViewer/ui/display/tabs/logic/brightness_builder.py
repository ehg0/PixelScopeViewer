"""BrightnessTab の widget 生成と layout。"""

import math

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
)

from PixelScopeViewer.ui.common import theme
from PixelScopeViewer.ui.common.widgets import StepSlider, make_spinbox, set_value_silently
from PixelScopeViewer.ui.display.tabs.components import PowerOfTwoSpinBox

SPINBOX_STYLESHEET = "QSpinBox, QDoubleSpinBox { padding: 10px; font-size: 10pt; }"


def build_dtype_selector(layout, current_dtype, on_dtype_changed_callback):
    """dtype の combo box を作成する。"""
    dtype_layout = QHBoxLayout()
    dtype_label = QLabel("データ型 (Data Type)")
    dtype_label.setStyleSheet("font-weight: bold; font-size: 10pt;")

    dtype_combo = QComboBox()
    dtype_combo.addItems(["float", "uint8", "uint16"])
    dtype_combo.setCurrentText(current_dtype)
    dtype_combo.currentTextChanged.connect(on_dtype_changed_callback)

    dtype_layout.addWidget(dtype_label)
    dtype_layout.addWidget(dtype_combo)
    dtype_layout.addStretch()

    layout.addLayout(dtype_layout)
    layout.addSpacing(10)
    return dtype_combo


def build_autoscale(layout, on_autoscale_cb_callback, set_as_default_callback):
    """auto scale と ROI 使用の checkbox、既定値に設定する button を作成する。

    Returns:
        (auto scale の checkbox, ROI 使用の checkbox, 既定値に設定する button)。
    """
    _layout = QHBoxLayout()

    autoscale_cb = QCheckBox("Auto Scale (min-max)")
    autoscale_cb.toggled.connect(on_autoscale_cb_callback)

    use_roi_cb = QCheckBox("Use Current ROI")
    use_roi_cb.toggled.connect(on_autoscale_cb_callback)

    set_ad_default_bt = QPushButton("Set as Default")
    set_ad_default_bt.clicked.connect(set_as_default_callback)

    _layout.addWidget(autoscale_cb)
    _layout.addWidget(use_roi_cb)
    _layout.addWidget(set_ad_default_bt)
    _layout.addStretch()

    layout.addLayout(_layout)
    layout.addSpacing(10)
    return autoscale_cb, use_roi_cb, set_ad_default_bt


def _add_slider_row(layout, caption: str, slider, spinbox, spacing: int | None = None):
    """右寄せの caption、slider、spin box を 4:1 の幅で並べた行を追加する。"""
    row = QHBoxLayout()
    if spacing is not None:
        row.setSpacing(spacing)
    label = QLabel(caption)
    label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    row.addWidget(label)
    row.addWidget(slider, 4)
    row.addWidget(spinbox, 1)
    layout.addLayout(row)


def _make_range_slider(value_range, value) -> QSlider:
    """範囲を 4 等分した目盛りを持つ横向きの slider を作成する。"""
    slider = QSlider(Qt.Horizontal)
    slider.setRange(int(value_range[0]), int(value_range[1]))
    slider.setTickPosition(QSlider.TicksBelow)
    slider.setTickInterval(int((value_range[1] - value_range[0]) // 4))
    slider.setStyleSheet(theme.SLIDER_STYLESHEET)
    set_value_silently(slider, int(value))
    return slider


def build_offset_controls(layout, initial_value, offset_range, is_float, slider_callback, spinbox_callback):
    """offset の slider と spin box を作成する。

    Returns:
        (slider, spin box)。
    """
    slider = _make_range_slider(offset_range, initial_value)
    slider.valueChanged.connect(slider_callback)
    spinbox = make_spinbox(
        offset_range, 5 if is_float else 0, 0.01 if is_float else 1, initial_value, stylesheet=SPINBOX_STYLESHEET
    )
    spinbox.valueChanged.connect(spinbox_callback)
    _add_slider_row(layout, "Offset", slider, spinbox, spacing=10)
    return slider, spinbox


def build_gain_controls(
    layout, initial_value, log2_min, log2_max, spinbox_min, spinbox_max, slider_callback, spinbox_callback
):
    """gain の slider（log2 scale）と spin box（2 の累乗で増減）を作成する。

    Returns:
        (slider, spin box)。
    """
    slider = StepSlider(Qt.Horizontal)
    slider.setRange(log2_min, log2_max)
    slider.setSingleStep(1)
    slider.setTickPosition(QSlider.TicksBelow)
    slider.setTickInterval(1)
    slider.setStyleSheet(theme.SLIDER_STYLESHEET)
    set_value_silently(slider, max(log2_min, min(log2_max, round(math.log2(initial_value)))))
    slider.valueChanged.connect(slider_callback)

    spinbox = make_spinbox(
        (spinbox_min, spinbox_max),
        7,
        1,
        initial_value,
        spinbox=PowerOfTwoSpinBox(log2_min=log2_min, log2_max=log2_max),
        stylesheet=SPINBOX_STYLESHEET,
    )
    spinbox.setFixedWidth(100)
    spinbox.valueChanged.connect(spinbox_callback)
    _add_slider_row(layout, "Gain", slider, spinbox)
    return slider, spinbox


def build_upper_level_controls(layout, initial_value, upper_level_range, is_float, slider_callback, spinbox_callback):
    """upper level の slider と spin box を作成する。

    Returns:
        (slider, spin box)。
    """
    slider = _make_range_slider(upper_level_range, initial_value)
    slider.valueChanged.connect(slider_callback)
    spinbox = make_spinbox(
        upper_level_range, 3 if is_float else 0, 10 if is_float else 1, initial_value, stylesheet=SPINBOX_STYLESHEET
    )
    spinbox.valueChanged.connect(spinbox_callback)
    _add_slider_row(layout, "Upper_level", slider, spinbox)
    return slider, spinbox


def build_formula_and_reset(layout, reset_callback):
    """変換式の label と reset button を作成する。

    Returns:
        reset button。
    """
    formula_label = QLabel("-> yout = gain × (yin - offset) / (upper_level - offset) × 255")
    formula_label.setStyleSheet("font-style: italic; font-size: 10pt")
    layout.addWidget(formula_label)

    reset_button = QPushButton("Reset (Ctrl+R)")
    reset_button.clicked.connect(reset_callback)
    layout.addWidget(reset_button)

    layout.addStretch()
    return reset_button
