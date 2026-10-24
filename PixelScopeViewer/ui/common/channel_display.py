"""channel の色・表示 ON/OFF・表示モードの唯一の持ち主。"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor

from PixelScopeViewer.ui.common import theme


def get_default_channel_colors(n_channels: int) -> list:
    """channel 数に応じた既定の QColor のリストを返す。

    1ch は白、2ch は赤・緑、3ch は RGB、4ch は RGB + 灰色、5ch 以上は hue を均等に割り当てる。
    """
    if n_channels == 1:
        return [QColor(theme.CHANNEL_COLOR_1CH)]

    # 2ch は optical flow を想定し、flow_x を赤、flow_y を緑にする
    if n_channels == 2:
        return [QColor.fromHsv(hue, 255, 255) for hue in theme.CHANNEL_HUES_2CH]

    if n_channels == 3:
        return [QColor(c) for c in theme.CHANNEL_COLORS_3CH]

    # RGBIR を想定
    if n_channels == 4:
        return [QColor(c) for c in theme.CHANNEL_COLORS_4CH]

    colors = []
    for i in range(n_channels):
        hue = int(360 * i / n_channels)
        color = QColor.fromHsv(hue, theme.CHANNEL_SATURATION_MANY, 255)
        colors.append(color)
    return colors


MODE_1CH_GRAYSCALE = "grayscale"
MODE_1CH_JET = "jet"

MODE_2CH_COMPOSITE = "composite"
MODE_2CH_FLOW_HSV = "flow-hsv"


class ChannelDisplay(QObject):
    """channel 数ごとの色・表示 ON/OFF と 1ch/2ch 画像の表示モードを保持し、変更を signal で通知する。

    ImageViewer が 1 つ作り、色を使う画面はこの instance を参照して signal を受け取る。
    色は hex 文字列で保持し、取得時に QColor を新しく作って返す。
    """

    colors_changed = Signal(int)  # 変更された channel 数
    checks_changed = Signal(int)
    modes_changed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._colors_by_n: dict[int, list[str]] = {}
        self._checks_by_n: dict[int, list[bool]] = {}
        self.mode_1ch: str = MODE_1CH_GRAYSCALE
        self.mode_2ch: str = MODE_2CH_FLOW_HSV

    # ---- 色 ----
    def colors(self, n_channels: int) -> list[QColor]:
        """channel 数に対応する色を返す。未設定の channel は既定色にする。"""
        if n_channels <= 0:
            return []
        stored = self._colors_by_n.get(n_channels, [])
        defaults = get_default_channel_colors(n_channels)
        return [QColor(stored[i]) if i < len(stored) else defaults[i] for i in range(n_channels)]

    def set_colors(self, n_channels: int, colors: list[QColor]) -> None:
        """channel 数に対応する色を設定する。不足分は既定色で補う。"""
        if n_channels <= 0:
            return
        defaults = get_default_channel_colors(n_channels)
        names = [QColor(colors[i] if i < len(colors) else defaults[i]).name() for i in range(n_channels)]
        if self._colors_by_n.get(n_channels) == names:
            return
        self._colors_by_n[n_channels] = names
        self.colors_changed.emit(n_channels)

    # ---- 表示 ON/OFF ----
    def checks(self, n_channels: int) -> list[bool]:
        """channel 数に対応する表示 ON/OFF を返す。未設定の channel は True（表示）にする。"""
        if n_channels <= 0:
            return []
        stored = self._checks_by_n.get(n_channels, [])
        return [stored[i] if i < len(stored) else True for i in range(n_channels)]

    def set_checks(self, n_channels: int, checks: list[bool]) -> None:
        """channel 数に対応する表示 ON/OFF を設定する。"""
        if n_channels <= 0:
            return
        fixed = [bool(checks[i]) if i < len(checks) else True for i in range(n_channels)]
        if self._checks_by_n.get(n_channels) == fixed:
            return
        self._checks_by_n[n_channels] = fixed
        self.checks_changed.emit(n_channels)

    # ---- 表示モード ----
    def set_mode_1ch(self, mode: str) -> None:
        if mode in (MODE_1CH_GRAYSCALE, MODE_1CH_JET) and mode != self.mode_1ch:
            self.mode_1ch = mode
            self.modes_changed.emit()

    def set_mode_2ch(self, mode: str) -> None:
        if mode in (MODE_2CH_COMPOSITE, MODE_2CH_FLOW_HSV) and mode != self.mode_2ch:
            self.mode_2ch = mode
            self.modes_changed.emit()

    def snapshot(self) -> dict:
        """現在の設定を channel 数ごとの dict で返す（状態の確認用）。"""
        return {
            "colors_by_n": {n: list(c) for n, c in self._colors_by_n.items()},
            "checks_by_n": {n: list(c) for n, c in self._checks_by_n.items()},
            "mode_1ch": self.mode_1ch,
            "mode_2ch": self.mode_2ch,
        }
