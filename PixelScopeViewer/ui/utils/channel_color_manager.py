"""Centralized channel color and display mode management.

This module keeps per-channel-count color lists and special display modes
for 1-channel and 2-channel images. It serves as the single source of truth
for color decisions to avoid duplication across viewer and dialogs.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List
from PySide6.QtGui import QColor

from .color_utils import get_default_channel_colors


MODE_1CH_GRAYSCALE = "grayscale"
MODE_1CH_JET = "jet"

MODE_2CH_COMPOSITE = "composite"
MODE_2CH_FLOW_HSV = "flow-hsv"


@dataclass
class ChannelColorManager:
    """Stores colors per channel count and display modes for 1ch/2ch.

    - Colors are keyed by channel count (n -> List[QColor]).
    - Channel visibility checks are keyed by channel count (n -> List[bool]).
    - Modes: 1ch (grayscale/jet), 2ch (composite/flow-hsv)
    """

    colors_by_n: Dict[int, List[QColor]] = field(default_factory=dict)
    checks_by_n: Dict[int, List[bool]] = field(default_factory=dict)
    mode_1ch: str = MODE_1CH_GRAYSCALE
    mode_2ch: str = MODE_2CH_FLOW_HSV  # Default: flow-hsv for 2ch

    def get_colors(self, n_channels: int) -> List[QColor]:
        """Return stored colors for this channel count, falling back to defaults.
        Ensures the length is exactly n_channels.
        """
        if n_channels <= 0:
            return []
        if n_channels not in self.colors_by_n:
            self.colors_by_n[n_channels] = get_default_channel_colors(n_channels)
        else:
            # extend or truncate to match n
            current = self.colors_by_n[n_channels]
            if len(current) < n_channels:
                defaults = get_default_channel_colors(n_channels)
                current = current + defaults[len(current) :]
                self.colors_by_n[n_channels] = current
            elif len(current) > n_channels:
                self.colors_by_n[n_channels] = current[:n_channels]
        return self.colors_by_n[n_channels]

    def set_colors(self, n_channels: int, colors: List[QColor]) -> None:
        """Set (override) the colors for a specific channel count.
        The list will be truncated/extended using defaults to match n.
        """
        if n_channels <= 0:
            return
        defaults = get_default_channel_colors(n_channels)
        fixed = [(colors[i] if i < len(colors) else defaults[i]) for i in range(n_channels)]
        self.colors_by_n[n_channels] = fixed

    def resolve_with_existing(self, n_channels: int, existing: List[QColor] | None) -> List[QColor]:
        """Resolve colors by combining an existing list with defaults, store and return it.
        Useful when migrating existing viewer state into the manager.
        """
        existing = existing or []
        defaults = get_default_channel_colors(n_channels)
        resolved = [existing[i] if i < len(existing) else defaults[i] for i in range(n_channels)]
        self.colors_by_n[n_channels] = resolved
        return resolved

    # ---- Mode helpers ----
    def set_mode_1ch(self, mode: str) -> None:
        if mode in (MODE_1CH_GRAYSCALE, MODE_1CH_JET):
            self.mode_1ch = mode

    def set_mode_2ch(self, mode: str) -> None:
        if mode in (MODE_2CH_COMPOSITE, MODE_2CH_FLOW_HSV):
            self.mode_2ch = mode

    # ---- Channel checks helpers ----
    def get_checks(self, n_channels: int) -> List[bool]:
        """Return stored channel visibility checks for this channel count.
        Defaults to all True (visible).
        """
        if n_channels <= 0:
            return []
        if n_channels not in self.checks_by_n:
            self.checks_by_n[n_channels] = [True] * n_channels
        else:
            # extend or truncate to match n
            current = self.checks_by_n[n_channels]
            if len(current) < n_channels:
                current = current + [True] * (n_channels - len(current))
                self.checks_by_n[n_channels] = current
            elif len(current) > n_channels:
                self.checks_by_n[n_channels] = current[:n_channels]
        return self.checks_by_n[n_channels]

    def set_checks(self, n_channels: int, checks: List[bool]) -> None:
        """Set channel visibility checks for a specific channel count."""
        if n_channels <= 0:
            return
        fixed = [(checks[i] if i < len(checks) else True) for i in range(n_channels)]
        self.checks_by_n[n_channels] = fixed
