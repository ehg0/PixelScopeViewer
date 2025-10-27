"""Custom SpinBox widget that steps by powers of 2."""

import math
from PySide6.QtWidgets import QDoubleSpinBox


class PowerOfTwoSpinBox(QDoubleSpinBox):
    """Custom spin box that steps by powers of 2."""

    def __init__(self, parent=None, log2_min=-7, log2_max=10):
        super().__init__(parent)
        self._log2_min = log2_min
        self._log2_max = log2_max

    def stepBy(self, steps):
        """Override to step by powers of 2."""
        current_value = self.value()
        if current_value <= 0:
            current_value = 1.0

        # Get current log2 value
        current_log2 = math.log2(current_value)

        # Round to nearest integer and apply steps
        current_log2_int = round(current_log2)
        new_log2 = current_log2_int + steps

        # Clamp to valid range
        new_log2 = max(self._log2_min, min(self._log2_max, new_log2))

        # Convert back to actual value
        new_value = 2**new_log2

        # Set the new value (this will trigger valueChanged signal)
        self.setValue(new_value)

    def textFromValue(self, value):
        """Override to display optimal decimal places for powers of 2."""
        if value <= 0:
            # Handle invalid values
            return "0"

        if value >= 1.0:
            # For values >= 1, display as integer
            return f"{int(value)}"
        else:
            # For fractional values (< 1), calculate minimal decimal places needed
            # Powers of 2 less than 1: 0.5, 0.25, 0.125, 0.0625, etc.
            log2_val = math.log2(value)
            decimals = max(1, abs(int(log2_val)))
            return f"{value:.{decimals}f}".rstrip("0").rstrip(".")
