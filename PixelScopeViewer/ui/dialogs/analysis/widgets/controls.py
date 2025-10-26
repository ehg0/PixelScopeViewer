"""Helper dialogs for analysis customization.

This module provides utility dialogs for:
- ChannelsDialog: Select which color channels to display in plots
"""

from typing import Optional
from PySide6.QtWidgets import QDialog, QVBoxLayout, QCheckBox


class ChannelsDialog(QDialog):
    """Dialog for selecting which channels to display in plots.

    Args:
        parent: Parent widget
        nch: Number of channels in the image
        checks: Initial checkbox states (list of bool)
        callback: Optional callback function to call when checkboxes change

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

    def __init__(self, parent, nch: int, checks: Optional[list] = None, callback=None):
        super().__init__(parent)
        self.setWindowTitle("Channels")
        self.setModal(False)  # Make it modeless since it's for immediate updates

        # Set a more appropriate default size
        self.resize(200, 150)

        self.callback = callback
        layout = QVBoxLayout(self)
        self.checks: list[QCheckBox] = []
        for i in range(nch):
            cb = QCheckBox(f"C{i}")
            cb.setChecked(checks[i] if checks and i < len(checks) else True)
            # Connect checkbox change to immediate update if callback provided
            if self.callback:
                cb.stateChanged.connect(self._on_checkbox_changed)
            layout.addWidget(cb)
            self.checks.append(cb)
        # No OK/Cancel buttons - immediate updates only

    def _on_checkbox_changed(self):
        """Called when any checkbox changes state - update graph immediately."""
        if self.callback:
            self.callback(self.results())

    def results(self) -> list[bool]:
        return [cb.isChecked() for cb in self.checks]
