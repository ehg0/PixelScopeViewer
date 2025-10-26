from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QGroupBox,
    QVBoxLayout as QV,
    QHBoxLayout,
    QLabel,
    QCheckBox,
    QPushButton,
    QColorDialog,
)
from PySide6.QtGui import QColor, QPixmap, QIcon


class ChannelTab(QWidget):
    """Tab for selecting visible channels and their colors."""

    channels_changed = Signal(list)  # list of bools for channel visibility
    channel_colors_changed = Signal(list)  # list of colors for channels

    def __init__(self, parent=None, image_array=None, image_path=None, initial_channels=None, initial_colors=None):
        super().__init__(parent)
        self.image_array = image_array
        self.checkboxes = []
        self.color_buttons = []
        self.channel_colors = []
        self._setup_ui(initial_channels, initial_colors)

    # ---------- UI helpers ----------
    def _default_colors(self, n_channels, given=None):
        """Return a length-n list of QColor defaults, preferring given when provided.
        - For 3 channels with no colors given, use RGB.
        - Otherwise default to white per channel.
        - If given is shorter than n, pad with white; if longer, truncate.
        """
        if given is not None:
            return [given[i] if i < len(given) else QColor(255, 255, 255) for i in range(n_channels)]
        if n_channels == 3:
            return [QColor(255, 0, 0), QColor(0, 255, 0), QColor(0, 0, 255)]
        return [QColor(255, 255, 255)] * n_channels

    def _update_color_button(self, button, color):
        pixmap = QPixmap(48, 16)
        pixmap.fill(color)
        button.setIcon(QIcon(pixmap))
        button.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #999;")
        button.setText("")

    def _emit_change(self):
        states = [cb.isChecked() for cb in self.checkboxes]
        self.channels_changed.emit(states)

    def _emit_color_change(self):
        self.channel_colors_changed.emit(self.channel_colors)

    def _make_channel_row(self, i, checked, color):
        row = QHBoxLayout()
        cb = QCheckBox(f"チャンネル {i} (Channel {i})")
        cb.setChecked(checked)
        cb.stateChanged.connect(self._on_channel_changed)
        self.checkboxes.append(cb)
        row.addWidget(cb)

        color_button = QPushButton()
        color_button.setFixedSize(60, 24)
        color_button.setToolTip("クリックして色を選択 (Click to select color)")
        self._update_color_button(color_button, color)
        color_button.clicked.connect(lambda checked=False, idx=i: self._select_color(idx))
        self.color_buttons.append(color_button)
        self.channel_colors.append(color)
        row.addWidget(color_button)
        row.addStretch()
        return row

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    # ---------- setup ----------
    def _setup_ui(self, initial_channels=None, initial_colors=None):
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)

        # Channel selection group
        channel_group = QGroupBox("表示チャンネル (Visible Channels)")
        channel_layout = QV(channel_group)
        self.checkboxes = []
        self.color_buttons = []
        self.channel_colors = []

        if self.image_array is not None and getattr(self.image_array, "ndim", 0) >= 3:
            n_channels = self.image_array.shape[2]
            resolved_colors = self._default_colors(n_channels, initial_colors)

            for i in range(n_channels):
                checked = initial_channels[i] if initial_channels and i < len(initial_channels) else True
                color = resolved_colors[i]
                row = self._make_channel_row(i, checked, color)
                channel_layout.addLayout(row)
        else:
            label = QLabel("チャンネル選択なし (グレースケール画像)")
            label.setStyleSheet("color: #888;")
            channel_layout.addWidget(label)

        layout.addWidget(channel_group)

        # Select All / Deselect All
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        self.select_all_btn = QPushButton("すべて選択 (Select All)")
        self.select_all_btn.clicked.connect(self.select_all)
        btn_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("すべて解除 (Deselect All)")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        btn_layout.addWidget(self.deselect_all_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()

    # ---------- events ----------
    def _on_channel_changed(self):
        self._emit_change()

    def _select_color(self, channel_idx):
        current_color = self.channel_colors[channel_idx]
        color = QColorDialog.getColor(current_color, self, f"チャンネル {channel_idx} の色を選択")
        if color.isValid():
            self.channel_colors[channel_idx] = color
            self._update_color_button(self.color_buttons[channel_idx], color)
            self._emit_color_change()

    # ---------- public API ----------
    def select_all(self):
        for cb in self.checkboxes:
            cb.setChecked(True)

    def deselect_all(self):
        for cb in self.checkboxes:
            cb.setChecked(False)

    def get_channel_states(self):
        return [cb.isChecked() for cb in self.checkboxes]

    def set_channel_states(self, states):
        for i, state in enumerate(states or []):
            if i < len(self.checkboxes):
                self.checkboxes[i].setChecked(state)

    def get_channel_colors(self):
        return self.channel_colors.copy()

    def set_channel_colors(self, colors):
        for i, color in enumerate(colors or []):
            if i < len(self.channel_colors):
                self.channel_colors[i] = color
                if i < len(self.color_buttons):
                    self._update_color_button(self.color_buttons[i], color)

    def update_for_new_image(self, image_array=None, channel_checks=None, channel_colors=None):
        self.image_array = image_array
        # Find or create group
        group = None
        for child in self.children():
            if isinstance(child, QGroupBox) and "チャンネル" in child.title():
                group = child
                break
        if group is None:
            return
        layout = group.layout()

        # Clear current UI
        self._clear_layout(layout)
        self.checkboxes.clear()
        self.color_buttons.clear()
        self.channel_colors.clear()

        # Rebuild
        if self.image_array is not None and getattr(self.image_array, "ndim", 0) >= 3:
            n_channels = self.image_array.shape[2]
            resolved_colors = self._default_colors(n_channels, channel_colors)

            for i in range(n_channels):
                checked = channel_checks[i] if channel_checks and i < len(channel_checks) else True
                color = resolved_colors[i]
                row = self._make_channel_row(i, checked, color)
                layout.addLayout(row)
        else:
            label = QLabel("チャンネル選択なし (グレースケール画像)")
            label.setStyleSheet("color: #888;")
            layout.addWidget(label)
