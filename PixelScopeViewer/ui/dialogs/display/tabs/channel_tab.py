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
    QRadioButton,
    QButtonGroup,
)
from PySide6.QtGui import QColor, QPixmap, QIcon
from ....utils import (
    get_default_channel_colors,
    colorbar_jet,
    colorbar_flow_hsv,
)
from PixelScopeViewer.core.image_io import numpy_to_qimage


class ChannelTab(QWidget):
    """Tab for selecting visible channels and their colors."""

    channels_changed = Signal(list)  # list of bools for channel visibility
    channel_colors_changed = Signal(list)  # list of colors for channels
    mode_1ch_changed = Signal(str)  # "grayscale" or "jet"
    mode_2ch_changed = Signal(str)  # "composite" or "flow-hsv"

    def __init__(
        self,
        parent=None,
        image_array=None,
        image_path=None,
        initial_channels=None,
        initial_colors=None,
        initial_mode_1ch: str | None = None,
        initial_mode_2ch: str | None = None,
    ):
        super().__init__(parent)
        self.image_array = image_array
        self.checkboxes = []
        self.color_buttons = []
        self.channel_colors = []
        self._mode1 = initial_mode_1ch or "grayscale"
        self._mode2 = initial_mode_2ch or "flow-hsv"  # Default to flow-hsv for 2ch
        self._colorbar_label = None
        self._mode_group_box = None
        self._mode_layout = None
        self._mode_controls_layout = None
        self._last_brightness = None  # (offset, gain, saturation)
        self._setup_ui(initial_channels, initial_colors)

    # ---------- UI helpers ----------
    def _default_colors(self, n_channels, given=None):
        """Return a length-n list of QColor defaults, preferring given when provided.

        If given is shorter than n, pad with default colors; if longer, truncate.
        """
        if given is not None and len(given) > 0:
            # Use given colors, and extend with default colors for missing channels
            default_colors = get_default_channel_colors(n_channels)
            return [given[i] if i < len(given) else default_colors[i] for i in range(n_channels)]

        return get_default_channel_colors(n_channels)

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

        self.reset_colors_btn = QPushButton("配色をリセット (Reset Colors)")
        self.reset_colors_btn.clicked.connect(self.reset_colors)
        btn_layout.addWidget(self.reset_colors_btn)

        layout.addLayout(btn_layout)

        # Display mode group for 1ch / 2ch (create once, reuse internal layouts)
        self._mode_group_box = QGroupBox("表示形式 (Display Mode)")
        self._mode_layout = QV(self._mode_group_box)
        self._mode_controls_layout = QVBoxLayout()
        self._mode_layout.addLayout(self._mode_controls_layout)
        self._colorbar_label = QLabel()
        self._colorbar_label.setAlignment(Qt.AlignCenter)
        # Don't set fixed height - let it adjust based on content
        self._mode_layout.addWidget(self._colorbar_label)
        # Build per current image (controls only)
        self._build_mode_controls(self._mode_controls_layout)
        layout.addWidget(self._mode_group_box)
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

    def reset_colors(self):
        """Reset channel colors to default (RGB for 3ch, white otherwise)."""
        n_channels = len(self.channel_colors)
        default_colors = self._default_colors(n_channels, given=None)
        for i in range(n_channels):
            self.channel_colors[i] = default_colors[i]
            if i < len(self.color_buttons):
                self._update_color_button(self.color_buttons[i], default_colors[i])
        self._emit_color_change()

    # ---------- display mode (1ch/2ch) ----------
    def _build_mode_controls(self, controls_layout):
        """Rebuild only the radio button controls in the controls_layout.
        The colorbar label is handled separately and not removed here.
        """
        # Clear existing radio buttons
        self._clear_layout(controls_layout)

        # Determine channel configuration
        ndim = getattr(self.image_array, "ndim", 0) if self.image_array is not None else 0
        nchan = self.image_array.shape[2] if (ndim >= 3) else (1 if ndim == 2 else 0)

        if nchan in (1, 2):
            if nchan == 1:
                # 1ch: grayscale vs JET
                group = QButtonGroup(self)
                rb_gray = QRadioButton("グレースケール")
                rb_jet = QRadioButton("擬似カラー (Jet)")
                group.addButton(rb_gray)
                group.addButton(rb_jet)
                # Block signals during initialization to prevent spurious mode changes
                rb_gray.blockSignals(True)
                rb_jet.blockSignals(True)
                rb_gray.setChecked(self._mode1 == "grayscale")
                rb_jet.setChecked(self._mode1 == "jet")
                rb_gray.blockSignals(False)
                rb_jet.blockSignals(False)
                # Now connect signals
                rb_gray.toggled.connect(lambda checked: self._on_mode1_changed("grayscale" if checked else None))
                rb_jet.toggled.connect(lambda checked: self._on_mode1_changed("jet" if checked else None))
                controls_layout.addWidget(rb_gray)
                controls_layout.addWidget(rb_jet)
            else:
                # 2ch: composite vs flow-hsv
                group = QButtonGroup(self)
                rb_comp = QRadioButton("色合成 (Composite)")
                rb_flow = QRadioButton("HSV (Flow)")
                group.addButton(rb_comp)
                group.addButton(rb_flow)
                # Block signals during initialization to prevent spurious mode changes
                rb_comp.blockSignals(True)
                rb_flow.blockSignals(True)
                rb_comp.setChecked(self._mode2 == "composite")
                rb_flow.setChecked(self._mode2 == "flow-hsv")
                rb_comp.blockSignals(False)
                rb_flow.blockSignals(False)
                # Now connect signals
                rb_comp.toggled.connect(lambda checked: self._on_mode2_changed("composite" if checked else None))
                rb_flow.toggled.connect(lambda checked: self._on_mode2_changed("flow-hsv" if checked else None))
                controls_layout.addWidget(rb_comp)
                controls_layout.addWidget(rb_flow)

            self._mode_group_box.setVisible(True)
            self._colorbar_label.setVisible(True)
            self._update_colorbar()
        else:
            self._mode_group_box.setVisible(False)
            self._colorbar_label.setVisible(False)

    def _update_colorbar(self):
        if self._colorbar_label is None:
            return
        # Determine channels again
        ndim = getattr(self.image_array, "ndim", 0) if self.image_array is not None else 0
        nchan = self.image_array.shape[2] if (ndim >= 3) else (1 if ndim == 2 else 0)
        if nchan == 1 and self._mode1 == "jet":
            # Compute labels based on brightness if available
            min_label = None
            max_label = None
            if self._last_brightness is not None:
                try:
                    off, gain, sat = self._last_brightness
                    # yout = gain*(yin - off)/sat*255 -> yin at 0 and 255
                    vmin = off
                    vmax = off + (sat / gain if gain not in (0, None) else 0)

                    def fmt(v):
                        if abs(v - round(v)) < 1e-6:
                            return str(int(round(v)))
                        return f"{v:.3f}"

                    min_label = fmt(vmin)
                    max_label = fmt(vmax)
                except Exception:
                    pass
            bar = colorbar_jet(256, 24, True, min_label=min_label, max_label=max_label)
        elif nchan == 2 and self._mode2 == "flow-hsv":
            # Circular HSV colorbar (no numeric labels)
            bar = colorbar_flow_hsv(256, 256, False)
        else:
            bar = None
        if bar is None:
            self._colorbar_label.clear()
            self._colorbar_label.setFixedSize(0, 0)
        else:
            qimg = numpy_to_qimage(bar)
            pixmap = QPixmap.fromImage(qimg)

            # Set appropriate size based on colorbar type
            if nchan == 2 and self._mode2 == "flow-hsv":
                # Circular colorbar: keep square aspect ratio, reasonable size
                self._colorbar_label.setFixedSize(200, 200)
                pixmap = pixmap.scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            else:
                # Linear colorbar (Jet): use original narrow height
                self._colorbar_label.setFixedSize(256, 30)
                pixmap = pixmap.scaled(256, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation)

            self._colorbar_label.setPixmap(pixmap)

    # Receive brightness updates for colorbar captions
    def on_brightness_for_colorbar(self, offset, gain, saturation):
        self._last_brightness = (offset, gain, saturation)
        self._update_colorbar()

    def _on_mode1_changed(self, mode: str | None):
        if mode is None:
            return
        if mode != self._mode1:
            self._mode1 = mode
            self._update_colorbar()
            self.mode_1ch_changed.emit(mode)

    def _on_mode2_changed(self, mode: str | None):
        if mode is None:
            return
        if mode != self._mode2:
            self._mode2 = mode
            self._update_colorbar()
            self.mode_2ch_changed.emit(mode)
        else:
            pass

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

        # Rebuild mode controls (reuse existing layouts/label)
        if self._mode_group_box is not None and self._mode_controls_layout is not None:
            self._build_mode_controls(self._mode_controls_layout)
            self._update_colorbar()
