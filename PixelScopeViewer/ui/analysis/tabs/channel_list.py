"""解析 dialog の channel ごとの表示 ON/OFF と色の一覧。"""

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
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
        # icon だと枠との間に余白ができるため、button の背景を塗りつぶす
        if color is None:
            button.setStyleSheet("")
            return
        fill = QColor(color).name()
        button.setStyleSheet(
            f"QPushButton {{ background-color: {fill}; border: 1px solid {theme.COLOR_BUTTON_BORDER}; }}"
        )


class RoiChannelPanel(QWidget):
    """登録 ROI ごとの channel の一覧。全選択・全解除の button の下に、R{id} の見出しと ChannelListWidget を並べる。

    ROI の組み合わせと channel 数が変わらない限り、ChannelListWidget を使い回す。
    """

    group_checks_changed = Signal(int, list)  # ROI の id, 表示 ON/OFF
    group_color_clicked = Signal(int, int)  # ROI の id, channel の index
    group_reset_requested = Signal(int)  # ROI の id
    all_checks_requested = Signal(bool)  # 全選択は True、全解除は False

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        buttons = QHBoxLayout()
        for text, value in (("全選択", True), ("全解除", False)):
            btn = QPushButton(text)
            btn.setMaximumWidth(80)
            btn.clicked.connect(lambda _checked=False, v=value: self.all_checks_requested.emit(v))
            buttons.addWidget(btn)
        buttons.addStretch()
        layout.addLayout(buttons)
        self._groups_layout = QVBoxLayout()
        self._groups_layout.setSpacing(3)
        layout.addLayout(self._groups_layout)
        self._lists: dict[int, ChannelListWidget] = {}
        self._structure: list[tuple[int, int]] = []

    def set_groups(self, groups: list[tuple[int, list[bool], list[QColor]]]) -> None:
        """ROI ごとの (id, 表示 ON/OFF, 色) で一覧を更新する。channel 数は表示 ON/OFF の数にする。"""
        structure = [(roi_id, len(checks)) for roi_id, checks, _ in groups]
        if structure != self._structure:
            self._rebuild(structure)
        for roi_id, checks, colors in groups:
            labels = [f"C{c}" for c in range(len(checks))] if len(checks) > 1 else ["Intensity"]
            self._lists[roi_id].set_channels(labels, checks, colors)

    def _rebuild(self, structure: list[tuple[int, int]]):
        while self._groups_layout.count():
            item = self._groups_layout.takeAt(0)
            if item.widget():
                # 削除されるまでの間に新しい行と重なって見えないよう、先に隠す
                item.widget().hide()
                item.widget().deleteLater()
        self._lists = {}
        for roi_id, n in structure:
            title = QLabel(f"R{roi_id}")
            title.setStyleSheet("font-weight: bold; margin-top: 5px;")
            self._groups_layout.addWidget(title)
            channel_list = ChannelListWidget(max_rows=n)
            channel_list.checks_changed.connect(lambda checks, r=roi_id: self.group_checks_changed.emit(r, checks))
            channel_list.color_clicked.connect(lambda c, r=roi_id: self.group_color_clicked.emit(r, c))
            channel_list.reset_requested.connect(lambda r=roi_id: self.group_reset_requested.emit(r))
            self._groups_layout.addWidget(channel_list)
            self._lists[roi_id] = channel_list
        self._structure = structure
