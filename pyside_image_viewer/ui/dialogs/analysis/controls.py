"""Helper dialogs for analysis customization.

This module provides utility dialogs for:
- ChannelsDialog: Select which color channels to display in plots
- RangesDialog: Set manual axis ranges for plots
"""

from typing import Optional, Tuple
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QCheckBox,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
)


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


class RangesDialog(QDialog):
    """Dialog for manually setting axis ranges in plots.

    Allows user to specify custom min/max values for X and Y axes.
    Empty fields are treated as None (auto range).

    Args:
        parent: Parent widget
        xmin, xmax, ymin, ymax: Initial range values (None for auto)

    Usage:
        dlg = RangesDialog(parent, xmin=0, xmax=100, ymin=None, ymax=255)
        if dlg.exec() == QDialog.Accepted:
            xmin, xmax, ymin, ymax = dlg.results()
    """

    def __init__(self, parent, xmin, xmax, ymin, ymax):
        super().__init__(parent)
        self.setWindowTitle("Axis ranges")
        self.setModal(True)
        layout = QFormLayout(self)
        self.xmin = QLineEdit()
        self.xmin.setText("" if xmin is None else str(xmin))
        self.xmax = QLineEdit()
        self.xmax.setText("" if xmax is None else str(xmax))
        self.ymin = QLineEdit()
        self.ymin.setText("" if ymin is None else str(ymin))
        self.ymax = QLineEdit()
        self.ymax.setText("" if ymax is None else str(ymax))
        layout.addRow("x min:", self.xmin)
        layout.addRow("x max:", self.xmax)
        layout.addRow("y min:", self.ymin)
        layout.addRow("y max:", self.ymax)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _parse(self, txt: str) -> Optional[float]:
        try:
            return float(txt) if txt is not None and txt != "" else None
        except Exception:
            return None

    def results(self) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
        return (
            self._parse(self.xmin.text()),
            self._parse(self.xmax.text()),
            self._parse(self.ymin.text()),
            self._parse(self.ymax.text()),
        )
