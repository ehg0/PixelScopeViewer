"""2 の累乗で増減する spin box。"""

import math

from PySide6.QtWidgets import QDoubleSpinBox


class PowerOfTwoSpinBox(QDoubleSpinBox):
    """2^log2_min 〜 2^log2_max の範囲を 2 の累乗で増減する QDoubleSpinBox。"""

    def __init__(self, parent=None, log2_min=-7, log2_max=10):
        super().__init__(parent)
        self._log2_min = log2_min
        self._log2_max = log2_max

    def stepBy(self, steps):
        current_value = self.value()
        if current_value <= 0:
            current_value = 1.0

        # 最も近い 2 の累乗から steps だけ進める
        current_log2 = math.log2(current_value)

        current_log2_int = round(current_log2)
        new_log2 = current_log2_int + steps

        new_log2 = max(self._log2_min, min(self._log2_max, new_log2))

        new_value = 2**new_log2

        self.setValue(new_value)

    def textFromValue(self, value):
        if value <= 0:
            return "0"

        if value >= 1.0:
            return f"{int(value)}"
        else:
            # 1 未満（0.5, 0.25, ...）は必要な桁数だけ表示する
            log2_val = math.log2(value)
            decimals = max(1, abs(int(log2_val)))
            return f"{value:.{decimals}f}".rstrip("0").rstrip(".")
