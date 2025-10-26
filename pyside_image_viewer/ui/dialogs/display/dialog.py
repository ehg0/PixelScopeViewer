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
    QTabWidget,
    QAbstractSpinBox,
)
from PySide6.QtCore import Qt, Signal
from .tabs import BrightnessTab, ChannelTab


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
        """Handle ESC key: clear spinbox focus if editing, otherwise prevent dialog close."""
        if event.key() == Qt.Key_Escape:
            fw = self.focusWidget()
            if isinstance(fw, QAbstractSpinBox):
                fw.clearFocus()
                event.accept()
            else:
                # Don't close dialog on ESC
                event.ignore()
            return
        super().keyPressEvent(event)
