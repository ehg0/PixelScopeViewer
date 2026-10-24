from PySide6.QtWidgets import QSlider


class StepSlider(QSlider):
    def wheelEvent(self, event):
        # ホイールの回転方向のみを取得 (上スクロール: 正 / 下スクロール: 負)
        delta = event.angleDelta().y()

        if delta > 0:
            self.setValue(self.value() + 1)
        elif delta < 0:
            self.setValue(self.value() - 1)

        # OS側の「3行スクロール」計算をキャンセル
        event.accept()
