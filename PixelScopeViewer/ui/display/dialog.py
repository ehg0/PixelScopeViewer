"""表示設定 dialog（brightness と channel の色・表示 ON/OFF）。"""

import contextlib

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QDialog,
    QTabWidget,
    QVBoxLayout,
)

from PixelScopeViewer.ui.common import defaults, theme
from PixelScopeViewer.ui.common.channel_display import MODE_1CH_GRAYSCALE, MODE_2CH_FLOW_HSV
from PixelScopeViewer.ui.display.tabs import BrightnessTab, ChannelTab


class BrightnessDialog(QDialog):
    """brightness と channel の色・表示 ON/OFF を設定する modeless dialog。

    Args:
        parent: 親 widget（通常は ImageViewer）。
        image_array: 画像配列。
        image_path: 画像ファイルのパス。
        initial_brightness: (offset, gain, upper_level) の初期値。
        initial_channels: channel ごとの表示 ON/OFF。
        initial_colors: channel ごとの QColor。
        initial_mode_1ch: 1ch 画像の表示モード。
        initial_mode_2ch: 2ch 画像の表示モード。
    """

    brightness_changed = Signal(float, float, float)  # offset, gain, upper_level
    channels_changed = Signal(list)  # channel ごとの表示 ON/OFF
    channel_colors_changed = Signal(list)  # channel ごとの QColor
    mode_1ch_changed = Signal(str)
    mode_2ch_changed = Signal(str)

    # 開き直したときに位置が変わらないよう geometry を class で保持する
    _saved_geometry = None
    # 最小化からの復元時に元の位置へ戻すため保持する
    _position_before_minimize = None

    def __init__(
        self,
        parent=None,
        image_array=None,
        image_path=None,
        initial_brightness=(0.0, 1.0, 255.0),
        initial_channels=None,
        initial_colors=None,
        initial_mode_1ch: str = MODE_1CH_GRAYSCALE,
        initial_mode_2ch: str = MODE_2CH_FLOW_HSV,
    ):
        super().__init__(parent)
        self.viewer = parent
        self.setWindowTitle("表示設定")
        self.resize(*defaults.DISPLAY_DIALOG_SIZE)
        self.setStyleSheet(f"QDialog {{ background-color: {theme.DIALOG_BACKGROUND}; }}")

        # 最小化を許可し、最前面に固定しない
        flags = Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.image_array = image_array
        self.image_path = image_path

        self.tabs = QTabWidget()

        self.channel_tab = ChannelTab(
            self,
            image_array,
            image_path,
            initial_channels,
            initial_colors,
            initial_mode_1ch,
            initial_mode_2ch,
        )
        self.tabs.addTab(self.channel_tab, "チャンネル色設定")

        self.brightness_tab = BrightnessTab(self, image_array, image_path)
        self.tabs.addTab(self.brightness_tab, "輝度調整")

        self.brightness_tab.brightness_changed.connect(self.brightness_changed)
        # colorbar の label 用に channel tab にも brightness を通知する
        self.brightness_tab.brightness_changed.connect(self.channel_tab.on_brightness_for_colorbar)
        self.channel_tab.channels_changed.connect(self.channels_changed)
        self.channel_tab.channels_changed.connect(self.brightness_tab._apply_autoscale)
        self.channel_tab.channel_colors_changed.connect(self.channel_colors_changed)
        self.channel_tab.mode_1ch_changed.connect(self.mode_1ch_changed)
        self.channel_tab.mode_2ch_changed.connect(self.mode_2ch_changed)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

        # 前回の geometry を復元する
        try:
            if BrightnessDialog._saved_geometry:
                self.restoreGeometry(BrightnessDialog._saved_geometry)
        except Exception:
            pass

        if initial_brightness:
            self.set_brightness(*initial_brightness)
            with contextlib.suppress(Exception):
                self.channel_tab.on_brightness_for_colorbar(*initial_brightness)
        if initial_channels:
            self.set_channels(initial_channels)
        if initial_colors:
            self.set_channel_colors(initial_colors)

    def set_brightness(self, offset, gain, upper_level):
        self.brightness_tab.offset_spinbox.setValue(offset)
        self.brightness_tab.gain_spinbox.setValue(gain)
        self.brightness_tab.upper_level_spinbox.setValue(upper_level)

    def set_gain(self, gain_value: float):
        self.brightness_tab.set_gain(gain_value)

    def reset_parameters(self):
        """brightness を初期値に戻し、brightness_changed を emit する。"""
        self.brightness_tab.reset_parameters()

    def set_channels(self, channels):
        self.channel_tab.set_channel_states(channels)

    def get_brightness(self):
        """(offset, gain, upper_level) を返す。"""
        return self.brightness_tab.get_parameters()

    def set_channel_colors(self, colors):
        self.channel_tab.set_channel_colors(colors)

    def update_for_new_image(
        self,
        image_array=None,
        image_path=None,
        keep_settings=True,
        channel_checks=None,
        channel_colors=None,
        initial_mode_1ch: str | None = None,
        initial_mode_2ch: str | None = None,
    ):
        """表示を新しい画像に合わせて更新する。モードが None の場合は現在のモードを保つ。"""
        self.image_array = image_array
        self.image_path = image_path
        self.brightness_tab.update_for_new_image(image_array, image_path, keep_settings)
        if initial_mode_1ch is not None:
            self.channel_tab._mode1 = initial_mode_1ch
        if initial_mode_2ch is not None:
            self.channel_tab._mode2 = initial_mode_2ch
        self.channel_tab.update_for_new_image(image_array, channel_checks, channel_colors)

    def changeEvent(self, event):
        # 最小化前の位置を保存し、復元時に戻す
        if event.type() == QEvent.WindowStateChange:
            if self.isMinimized():
                BrightnessDialog._position_before_minimize = self.pos()
            elif event.oldState() & Qt.WindowMinimized and BrightnessDialog._position_before_minimize is not None:
                self.move(BrightnessDialog._position_before_minimize)
        super().changeEvent(event)

    def moveEvent(self, event):
        with contextlib.suppress(Exception):
            BrightnessDialog._saved_geometry = self.saveGeometry()
        super().moveEvent(event)

    def resizeEvent(self, event):
        with contextlib.suppress(Exception):
            BrightnessDialog._saved_geometry = self.saveGeometry()
        super().resizeEvent(event)

    def keyPressEvent(self, event):
        # Esc で dialog を閉じず、spin box の focus を外すだけにする
        if event.key() == Qt.Key_Escape:
            fw = self.focusWidget()
            if isinstance(fw, QAbstractSpinBox):
                fw.clearFocus()
                event.accept()
            else:
                event.ignore()
            return
        super().keyPressEvent(event)
