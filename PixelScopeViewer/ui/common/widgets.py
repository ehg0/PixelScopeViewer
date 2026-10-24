"""汎用の custom Qt widget。"""

from PySide6.QtWidgets import QSlider


class StepSlider(QSlider):
    """wheel 1 回で 1 step だけ動く QSlider。"""

    def wheelEvent(self, event):
        # 回転方向のみを使う（上: 正 / 下: 負）
        delta = event.angleDelta().y()

        if delta > 0:
            self.setValue(self.value() + 1)
        elif delta < 0:
            self.setValue(self.value() - 1)

        # OS 側の複数行 scroll を打ち消す
        event.accept()
