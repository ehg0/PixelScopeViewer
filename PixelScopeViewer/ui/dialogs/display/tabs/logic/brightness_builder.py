"""UI builder for BrightnessTab - handles all widget creation and layout."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QSlider,
    QDoubleSpinBox,
    QPushButton,
    QComboBox,
)

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
        dtype_label = QLabel("データ型 (Data Type):")
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
            tuple: (value_label, slider, spinbox)
        """
        # Label with value
        label_layout = QHBoxLayout()
        title_label = QLabel("オフセット (Offset)")
        title_label.setStyleSheet("font-weight: bold; font-size: 10pt;")

        value_label = QLabel(f"{initial_value:.0f}" if not is_float else f"{initial_value:.5f}")
        value_label.setStyleSheet("color: #555; font-size: 10pt;")

        label_layout.addWidget(title_label)
        label_layout.addWidget(value_label)
        label_layout.addStretch()
        layout.addLayout(label_layout)

        # Controls
        control_layout = QHBoxLayout()
        control_layout.setSpacing(10)

        caption = QLabel("Offset")
        caption.setStyleSheet("font-size: 9pt; color: #888; min-width: 50px;")
        caption.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        control_layout.addWidget(caption)

        slider = QSlider(Qt.Horizontal)
        slider.setRange(int(offset_range[0] * 10), int(offset_range[1] * 10))
        slider.setTickPosition(QSlider.TicksBelow)
        slider.setTickInterval((offset_range[1] - offset_range[0]) // 4)
        slider.setStyleSheet(self.SLIDER_STYLESHEET)
        slider.blockSignals(True)
        slider.setValue(int(initial_value * 10))
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

        self.widgets["offset_value_label"] = value_label
        self.widgets["offset_slider"] = slider
        self.widgets["offset_spinbox"] = spinbox

        return value_label, slider, spinbox

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
            tuple: (value_label, slider, spinbox)
        """
        import math

        # Label with value
        label_layout = QHBoxLayout()
        title_label = QLabel("ゲイン (Gain)")
        title_label.setStyleSheet("font-weight: bold; font-size: 10pt;")
        title_label.setToolTip("ゲイン×0.5 : <,  ゲイン×2 : >")

        value_label = QLabel(f"{initial_value:.2f}")
        value_label.setStyleSheet("color: #555; font-size: 10pt;")

        label_layout.addWidget(title_label)
        label_layout.addWidget(value_label)
        label_layout.addStretch()
        layout.addLayout(label_layout)

        # Controls
        control_layout = QHBoxLayout()
        caption = QLabel("Gain")
        caption.setStyleSheet("font-size: 9pt; color: #888; min-width: 50px;")
        caption.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        control_layout.addWidget(caption)

        # Slider uses log2 scale
        slider = QSlider(Qt.Horizontal)
        slider.setRange(log2_min, log2_max)
        slider.setTickPosition(QSlider.TicksBelow)
        slider.setTickInterval(1)
        slider.setStyleSheet(self.SLIDER_STYLESHEET)
        slider.blockSignals(True)
        initial_log2 = int(round(math.log2(initial_value)))
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

        self.widgets["gain_value_label"] = value_label
        self.widgets["gain_slider"] = slider
        self.widgets["gain_spinbox"] = spinbox

        return value_label, slider, spinbox

    def build_saturation_controls(
        self,
        layout,
        initial_value,
        saturation_range,
        is_float,
        slider_callback,
        spinbox_callback,
    ):
        """Build saturation label, slider and spinbox controls.

        Args:
            layout: QVBoxLayout to add to
            initial_value: Initial saturation value
            saturation_range: Tuple (min, max)
            is_float: Whether values are float type
            slider_callback: Callback for slider changes
            spinbox_callback: Callback for spinbox changes

        Returns:
            tuple: (value_label, slider, spinbox)
        """
        # Label with value
        label_layout = QHBoxLayout()
        title_label = QLabel("飽和レベル (Saturation)")
        title_label.setStyleSheet("font-weight: bold; font-size: 10pt;")

        value_label = QLabel(f"{initial_value:.0f}" if not is_float else f"{initial_value:.5f}")
        value_label.setStyleSheet("color: #555; font-size: 10pt;")

        label_layout.addWidget(title_label)
        label_layout.addWidget(value_label)
        label_layout.addStretch()
        layout.addLayout(label_layout)

        # Controls
        control_layout = QHBoxLayout()
        caption = QLabel("Saturation")
        caption.setStyleSheet("font-size: 9pt; color: #888; min-width: 50px;")
        caption.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        control_layout.addWidget(caption)

        slider = QSlider(Qt.Horizontal)
        slider.setTickPosition(QSlider.TicksBelow)
        slider.setStyleSheet(self.SLIDER_STYLESHEET)

        if is_float:
            slider.setRange(int(saturation_range[0] * 1000), int(saturation_range[1] * 1000))
            slider.setTickInterval(int((saturation_range[1] - saturation_range[0]) * 1000 / 4))
            slider.blockSignals(True)
            slider.setValue(int(initial_value * 1000))
            slider.blockSignals(False)
        else:
            slider.setRange(saturation_range[0], saturation_range[1])
            slider.setTickInterval((saturation_range[1] - saturation_range[0]) // 4)
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
        spinbox.setRange(saturation_range[0], saturation_range[1])
        spinbox.setStyleSheet(self.SPINBOX_STYLESHEET)
        spinbox.blockSignals(True)
        spinbox.setValue(initial_value)
        spinbox.blockSignals(False)
        spinbox.valueChanged.connect(spinbox_callback)

        control_layout.addWidget(slider, 4)
        control_layout.addWidget(spinbox, 1)
        layout.addLayout(control_layout)

        self.widgets["saturation_value_label"] = value_label
        self.widgets["saturation_slider"] = slider
        self.widgets["saturation_spinbox"] = spinbox

        return value_label, slider, spinbox

    def build_formula_and_reset(self, layout, reset_callback):
        """Build formula label and reset button.

        Args:
            layout: QVBoxLayout to add to
            reset_callback: Callback for reset button

        Returns:
            QPushButton: The reset button
        """
        formula_label = QLabel("-> yout = gain × (yin - offset) / saturation × 255")
        formula_label.setStyleSheet("font-style: italic; font-size: 10pt")
        layout.addWidget(formula_label)

        reset_button = QPushButton("Reset (Ctrl+R)")
        reset_button.clicked.connect(reset_callback)
        layout.addWidget(reset_button)

        layout.addStretch()

        self.widgets["reset_button"] = reset_button
        return reset_button

    def get_widget(self, name):
        """Get a widget by name.

        Args:
            name: Widget identifier

        Returns:
            The widget, or None if not found
        """
        return self.widgets.get(name)
