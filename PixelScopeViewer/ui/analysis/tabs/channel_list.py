"""解析 dialog の channel ごとの表示 ON/OFF と色の一覧。"""

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import QCheckBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from PixelScopeViewer.ui.common import defaults, theme


class ChannelListWidget(QWidget):
    """`[checkbox] label [色]` の行を並べ、表示 ON/OFF と色ボタンのクリックを signal で通知する。

    行は最大 max_rows 行を先に作り、set_channels で表示する行数と内容を切り替える。
    """

    checks_changed = Signal(list)  # 表示中の行の ON/OFF
    color_clicked = Signal(int)  # 行の index
    reset_requested = Signal()

    def __init__(self, max_rows: int = defaults.MAX_CHANNEL_CHECKBOXES, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self._n_rows = 0
        self._rows: list[QWidget] = []
        self._checkboxes: list[QCheckBox] = []
        self._labels: list[QLabel] = []
        self._color_buttons: list[QPushButton] = []
        for i in range(max_rows):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            cb = QCheckBox()
            cb.stateChanged.connect(self._emit_checks)
            label = QLabel()
            button = QPushButton()
            button.setFixedSize(40, 18)
            button.setToolTip("クリックして色を選択")
            button.clicked.connect(lambda _=False, idx=i: self.color_clicked.emit(idx))
            row_layout.addWidget(cb)
            row_layout.addWidget(label)
            row_layout.addWidget(button)
            row_layout.addStretch()
            row.setVisible(False)
            layout.addWidget(row)
            self._rows.append(row)
            self._checkboxes.append(cb)
            self._labels.append(label)
            self._color_buttons.append(button)

        self.reset_button = QPushButton("色を戻す")
        self.reset_button.setMaximumWidth(80)
        self.reset_button.clicked.connect(self.reset_requested)
        layout.addWidget(self.reset_button)

    def set_channels(self, labels: list[str], checks: list[bool], colors: list[QColor]) -> None:
        """表示する行の label・ON/OFF・色を設定する。行数は labels の数にする。"""
        self._n_rows = min(len(labels), len(self._rows))
        for i, row in enumerate(self._rows):
            if i >= len(labels):
                row.setVisible(False)
                continue
            row.setVisible(True)
            self._labels[i].setText(labels[i])
            cb = self._checkboxes[i]
            # 更新中に signal が再帰的に発火しないようにする
            cb.blockSignals(True)
            cb.setChecked(checks[i] if i < len(checks) else True)
            cb.blockSignals(False)
            self._set_button_color(self._color_buttons[i], colors[i] if i < len(colors) else None)

    def checks(self) -> list[bool]:
        # isVisible は親が非表示だと False になるため、行数で判定する
        return [cb.isChecked() for cb in self._checkboxes[: self._n_rows]]

    def _emit_checks(self):
        self.checks_changed.emit(self.checks())

    @staticmethod
    def _set_button_color(button: QPushButton, color: QColor | None):
        if color is None:
            button.setIcon(QIcon())
            return
        pixmap = QPixmap(32, 12)
        pixmap.fill(QColor(color))
        button.setIcon(QIcon(pixmap))
        button.setIconSize(pixmap.size())
        button.setStyleSheet(f"border: 1px solid {theme.COLOR_BUTTON_BORDER};")
