"""Small control dialogs used by Analysis (channels, ranges)."""

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
    def __init__(self, parent, nch: int, checks: Optional[list] = None):
        super().__init__(parent)
        self.setWindowTitle("Channels")
        self.setModal(True)
        layout = QVBoxLayout(self)
        self.checks: list[QCheckBox] = []
        for i in range(nch):
            cb = QCheckBox(f"C{i}")
            cb.setChecked(checks[i] if checks and i < len(checks) else True)
            layout.addWidget(cb)
            self.checks.append(cb)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def results(self) -> list[bool]:
        return [cb.isChecked() for cb in self.checks]


class RangesDialog(QDialog):
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
