"""Helper dialogs for analysis customization.

This module provides utility dialogs for:
- ChannelsDialog: Select which color channels to display in plots
"""

from typing import Optional
from PySide6.QtWidgets import QDialog, QVBoxLayout, QCheckBox
from PySide6.QtGui import QPixmap, QColor


class ChannelsDialog(QDialog):
    """Dialog for selecting which channels to display in plots.

    Args:
        parent: Parent widget
        nch: Number of channels in the image
        checks: Initial checkbox states (list of bool)
        callback: Optional callback function to call when checkboxes change
        channel_colors: Optional list of QColor objects for channel colors

    Usage:
        dlg = ChannelsDialog(parent, nch=3, checks=[True, True, False])
        if dlg.exec() == QDialog.Accepted:
            selected = dlg.results()  # Returns list of bool

        # With immediate update:
        def update_callback(checks):
            # Update graph immediately
            pass
        dlg = ChannelsDialog(parent, nch=3, checks=[True, True, False], callback=update_callback)
    """

    MAX_CHANNELS = 8  # Maximum number of channels to support

    def __init__(
        self, parent, nch: int, checks: Optional[list] = None, callback=None, channel_colors: Optional[list] = None
    ):
        super().__init__(parent)
        self.setWindowTitle("Channels")
        self.setModal(False)  # Make it modeless since it's for immediate updates

        self.callback = callback
        self.nch = nch
        self.channel_colors = channel_colors
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        self.layout = layout
        self.checks: list[QCheckBox] = []

        # Create MAX_CHANNELS checkboxes upfront
        for i in range(self.MAX_CHANNELS):
            cb = QCheckBox(f"C{i}")
            cb.stateChanged.connect(self._on_checkbox_changed)
            self.layout.addWidget(cb)
            self.checks.append(cb)

        # Add stretch at the bottom to keep checkboxes at the top
        layout.addStretch()

        # Set fixed size to prevent checkbox position from shifting
        self.setFixedSize(200, 200)

        # Initialize visibility and states for current image
        self._update_checkboxes(nch, checks)

    def _update_checkboxes(self, nch: int, checks: Optional[list] = None):
        """Update checkbox visibility and states for the current image.

        Args:
            nch: Number of channels in current image
            checks: Checkbox states (optional)
        """
        for i in range(self.MAX_CHANNELS):
            cb = self.checks[i]
            if i < nch:
                # This channel exists in the current image
                cb.setVisible(True)
                cb.setChecked(checks[i] if checks and i < len(checks) else True)
                # Disable checkbox if only 1 channel (can't uncheck the only channel)
                cb.setEnabled(nch > 1)
                # Add color swatch icon if channel_colors provided
                if self.channel_colors and i < len(self.channel_colors):
                    color = self.channel_colors[i]
                    if hasattr(color, "name"):
                        pix = QPixmap(14, 14)
                        pix.fill(color)
                        cb.setIcon(pix)
                        cb.setIconSize(pix.size())
            else:
                # This channel doesn't exist in current image - hide it
                cb.setVisible(False)

    def update_for_new_image(self, nch: int, checks: Optional[list] = None, channel_colors: Optional[list] = None):
        """Update dialog for new image with different channel count.

        Args:
            nch: New number of channels
            checks: New checkbox states (optional)
            channel_colors: Optional list of QColor objects for channel colors
        """
        self.nch = nch
        self.channel_colors = channel_colors
        self._update_checkboxes(nch, checks)

    def _on_checkbox_changed(self):
        """Called when any checkbox changes state - update graph immediately."""
        if self.callback:
            self.callback(self.results())

    def results(self) -> list[bool]:
        """Return the checked state of visible checkboxes only."""
        return [cb.isChecked() for cb in self.checks[: self.nch]]
