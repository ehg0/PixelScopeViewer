"""UI builder for BrightnessTab - handles all widget creation and layout."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
)

from .....utils.custom_qtwidgets import StepSlider
from ..components import PowerOfTwoSpinBox


class BrightnessUIBuilder:
    """Responsible for building all UI components for BrightnessTab."""

    SLIDER_STYLESHEET = """
        QSlider::groove:horizontal { background: #ddd; height: 6px; border-radius: 3px; }
        QSlider::handle:horizontal { background: #666; width: 16px; margin: -5px 0; border-radius: 8px; }
        QSlider::handle:horizontal:hover { background: #444; }
    """

    SPINBOX_STYLESHEET = "QSpinBox, QDoubleSpinBox { padding: 10px; font-size: 10pt; }"

    def __init__(self, parent_widget):
        """Initialize the UI builder.

        Args:
            parent_widget: The parent widget to build UI on
        """
        self.parent = parent_widget
        self.widgets = {}

    def build_dtype_selector(self, layout, current_dtype, on_dtype_changed_callback):
        """Build the dtype selector combo box.

        Args:
            layout: QVBoxLayout to add to
            current_dtype: Current dtype string
            on_dtype_changed_callback: Callback for dtype changes
        """
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

        self.widgets["dtype_combo"] = dtype_combo
        return dtype_combo

    def build_autoscale(self, layout, on_autoscale_cb_callback, set_as_default_callback):
        # group = QGroupBox("Auto Scale (Range: min-max)")
        # group.setStyleSheet("""QGroupBox {font-weight: bold;font-size: 10pt;}""")
        # _layout = QHBoxLayout(group)
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

        # layout.addWidget(group)
        layout.addLayout(_layout)
        layout.addSpacing(10)

        return autoscale_cb, use_roi_cb, set_ad_default_bt

    def build_offset_controls(
        self,
        layout,
        initial_value,
        offset_range,
        is_float,
        slider_callback,
        spinbox_callback,
    ):
        """Build offset label, slider and spinbox controls.

        Args:
            layout: QVBoxLayout to add to
            initial_value: Initial offset value
            offset_range: Tuple (min, max)
            is_float: Whether values are float type
            slider_callback: Callback for slider changes
            spinbox_callback: Callback for spinbox changes

        Returns:
            tuple: (slider, spinbox)
        """
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)

        caption = QLabel("Offset")
        caption.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        control_layout.addWidget(caption)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(int(offset_range[0]), int(offset_range[1]))
        slider.setTickPosition(QSlider.TicksBelow)
        slider.setTickInterval((offset_range[1] - offset_range[0]) // 4)
        slider.setStyleSheet(self.SLIDER_STYLESHEET)
        slider.blockSignals(True)
        slider.setValue(int(initial_value))
        slider.blockSignals(False)
        slider.valueChanged.connect(slider_callback)

        spinbox = QDoubleSpinBox()
        if is_float:
            spinbox.setDecimals(5)
            spinbox.setSingleStep(0.01)
        else:
            spinbox.setDecimals(0)
            spinbox.setSingleStep(1)
        spinbox.setReadOnly(False)
        spinbox.setKeyboardTracking(True)
        spinbox.setRange(offset_range[0], offset_range[1])
        spinbox.setStyleSheet(self.SPINBOX_STYLESHEET)
        spinbox.blockSignals(True)
        spinbox.setValue(initial_value)
        spinbox.blockSignals(False)
        spinbox.valueChanged.connect(spinbox_callback)

        control_layout.addWidget(slider, 4)
        control_layout.addWidget(spinbox, 1)
        layout.addLayout(control_layout)

        self.widgets["offset_slider"] = slider
        self.widgets["offset_spinbox"] = spinbox

        return slider, spinbox

    def build_gain_controls(
        self,
        layout,
        initial_value,
        log2_min,
        log2_max,
        spinbox_min,
        spinbox_max,
        slider_callback,
        spinbox_callback,
    ):
        """Build gain label, slider and spinbox controls.

        Args:
            layout: QVBoxLayout to add to
            initial_value: Initial gain value
            log2_min: Minimum log2 value for slider
            log2_max: Maximum log2 value for slider
            spinbox_min: Minimum spinbox value
            spinbox_max: Maximum spinbox value
            slider_callback: Callback for slider changes
            spinbox_callback: Callback for spinbox changes

        Returns:
            tuple: (slider, spinbox)
        """
        import math

        control_layout = QHBoxLayout()
        caption = QLabel("Gain")
        caption.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        control_layout.addWidget(caption)

        # Slider uses log2 scale
        slider = StepSlider(Qt.Horizontal)
        slider.setRange(log2_min, log2_max)
        slider.setSingleStep(1)
        slider.setTickPosition(QSlider.TicksBelow)
        slider.setTickInterval(1)
        slider.setStyleSheet(self.SLIDER_STYLESHEET)
        slider.blockSignals(True)
        initial_log2 = round(math.log2(initial_value))
        initial_log2 = max(log2_min, min(log2_max, initial_log2))
        slider.setValue(initial_log2)
        slider.blockSignals(False)
        slider.valueChanged.connect(slider_callback)

        # Spinbox with power-of-2 stepping
        spinbox = PowerOfTwoSpinBox(log2_min=log2_min, log2_max=log2_max)
        spinbox.setDecimals(7)
        spinbox.setSingleStep(1)
        spinbox.setReadOnly(False)
        spinbox.setKeyboardTracking(True)
        spinbox.setRange(spinbox_min, spinbox_max)
        spinbox.setFixedWidth(100)
        spinbox.setStyleSheet(self.SPINBOX_STYLESHEET)
        spinbox.blockSignals(True)
        spinbox.setValue(initial_value)
        spinbox.blockSignals(False)
        spinbox.valueChanged.connect(spinbox_callback)

        control_layout.addWidget(slider, 4)
        control_layout.addWidget(spinbox, 1)
        layout.addLayout(control_layout)

        self.widgets["gain_slider"] = slider
        self.widgets["gain_spinbox"] = spinbox

        return slider, spinbox

    def build_upper_level_controls(
        self,
        layout,
        initial_value,
        upper_level_range,
        is_float,
        slider_callback,
        spinbox_callback,
    ):
        """Build upper_level label, slider and spinbox controls.

        Args:
            layout: QVBoxLayout to add to
            initial_value: Initial upper_level value
            upper_level_range: Tuple (min, max)
            is_float: Whether values are float type
            slider_callback: Callback for slider changes
            spinbox_callback: Callback for spinbox changes

        Returns:
            tuple: (slider, spinbox)
        """
        control_layout = QHBoxLayout()
        caption = QLabel("Upper_level")
        caption.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        control_layout.addWidget(caption)

        slider = QSlider(Qt.Horizontal)
        slider.setTickPosition(QSlider.TicksBelow)
        slider.setStyleSheet(self.SLIDER_STYLESHEET)

        slider.setRange(int(upper_level_range[0]), int(upper_level_range[1]))
        slider.setTickInterval(int((upper_level_range[1] - upper_level_range[0]) // 4))
        slider.blockSignals(True)
        slider.setValue(int(initial_value))
        slider.blockSignals(False)

        slider.valueChanged.connect(slider_callback)

        spinbox = QDoubleSpinBox()
        if is_float:
            spinbox.setDecimals(3)
            spinbox.setSingleStep(10)
        else:
            spinbox.setDecimals(0)
            spinbox.setSingleStep(1)
        spinbox.setReadOnly(False)
        spinbox.setKeyboardTracking(True)
        spinbox.setRange(upper_level_range[0], upper_level_range[1])
        spinbox.setStyleSheet(self.SPINBOX_STYLESHEET)
        spinbox.blockSignals(True)
        spinbox.setValue(initial_value)
        spinbox.blockSignals(False)
        spinbox.valueChanged.connect(spinbox_callback)

        control_layout.addWidget(slider, 4)
        control_layout.addWidget(spinbox, 1)
        layout.addLayout(control_layout)

        self.widgets["upper_level_slider"] = slider
        self.widgets["upper_level_spinbox"] = spinbox

        return slider, spinbox

    def build_formula_and_reset(self, layout, reset_callback):
        """Build formula label and reset button.

        Args:
            layout: QVBoxLayout to add to
            reset_callback: Callback for reset button

        Returns:
            QPushButton: The reset button
        """
        formula_label = QLabel("-> yout = gain × (yin - offset) / (upper_level - offset) × 255")
        formula_label.setStyleSheet("font-style: italic; font-size: 10pt")
        layout.addWidget(formula_label)

        reset_button = QPushButton("Reset (Ctrl+R)")
        reset_button.clicked.connect(reset_callback)
        layout.addWidget(reset_button)

        layout.addStretch()

        self.widgets["reset_button"] = reset_button
        return reset_button
