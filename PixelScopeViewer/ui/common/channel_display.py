"""channel の色と表示モードを一元管理する。"""

from __future__ import annotations

from dataclasses import dataclass, field

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


@dataclass
class ChannelColorManager:
    """channel 数ごとの色・表示 ON/OFF と、1ch/2ch 画像の表示モードを保持する。"""

    colors_by_n: dict[int, list[QColor]] = field(default_factory=dict)
    checks_by_n: dict[int, list[bool]] = field(default_factory=dict)
    mode_1ch: str = MODE_1CH_GRAYSCALE
    mode_2ch: str = MODE_2CH_FLOW_HSV

    def get_colors(self, n_channels: int) -> list[QColor]:
        """channel 数に対応する色を返す。未設定や不足分は既定色で補い、長さを n_channels に揃える。"""
        if n_channels <= 0:
            return []
        if n_channels not in self.colors_by_n:
            self.colors_by_n[n_channels] = get_default_channel_colors(n_channels)
        else:
            current = self.colors_by_n[n_channels]
            if len(current) < n_channels:
                defaults = get_default_channel_colors(n_channels)
                current = current + defaults[len(current) :]
                self.colors_by_n[n_channels] = current
            elif len(current) > n_channels:
                self.colors_by_n[n_channels] = current[:n_channels]
        return self.colors_by_n[n_channels]

    def set_colors(self, n_channels: int, colors: list[QColor]) -> None:
        """channel 数に対応する色を設定する。不足分は既定色で補う。"""
        if n_channels <= 0:
            return
        defaults = get_default_channel_colors(n_channels)
        fixed = [(colors[i] if i < len(colors) else defaults[i]) for i in range(n_channels)]
        self.colors_by_n[n_channels] = fixed

    def resolve_with_existing(self, n_channels: int, existing: list[QColor] | None) -> list[QColor]:
        """既存の色リストの不足分を既定色で補って保存し、返す。"""
        existing = existing or []
        defaults = get_default_channel_colors(n_channels)
        resolved = [existing[i] if i < len(existing) else defaults[i] for i in range(n_channels)]
        self.colors_by_n[n_channels] = resolved
        return resolved

    # ---- 表示モード ----
    def set_mode_1ch(self, mode: str) -> None:
        if mode in (MODE_1CH_GRAYSCALE, MODE_1CH_JET):
            self.mode_1ch = mode

    def set_mode_2ch(self, mode: str) -> None:
        if mode in (MODE_2CH_COMPOSITE, MODE_2CH_FLOW_HSV):
            self.mode_2ch = mode

    # ---- channel の表示 ON/OFF ----
    def get_checks(self, n_channels: int) -> list[bool]:
        """channel 数に対応する表示 ON/OFF を返す。未設定や不足分は True（表示）にする。"""
        if n_channels <= 0:
            return []
        if n_channels not in self.checks_by_n:
            self.checks_by_n[n_channels] = [True] * n_channels
        else:
            current = self.checks_by_n[n_channels]
            if len(current) < n_channels:
                current = current + [True] * (n_channels - len(current))
                self.checks_by_n[n_channels] = current
            elif len(current) > n_channels:
                self.checks_by_n[n_channels] = current[:n_channels]
        return self.checks_by_n[n_channels]

    def set_checks(self, n_channels: int, checks: list[bool]) -> None:
        """channel 数に対応する表示 ON/OFF を設定する。"""
        if n_channels <= 0:
            return
        fixed = [(checks[i] if i < len(checks) else True) for i in range(n_channels)]
        self.checks_by_n[n_channels] = fixed
