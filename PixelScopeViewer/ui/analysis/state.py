"""解析 dialog の現在の設定。"""

import copy
from dataclasses import dataclass, field

from PixelScopeViewer.ui.common import defaults


@dataclass
class AnalysisSettings:
    """profile・histogram の表示設定と、channel の表示 ON/OFF。"""

    profile_orientation: str = defaults.PROFILE_ORIENTATION  # "h", "v"
    profile_x_mode: str = defaults.PROFILE_X_MODE  # "relative", "absolute"
    profile_method: str = defaults.PROFILE_METHOD  # "mean", "std", "max", "min", "p2p", "median"
    hist_mode: str = defaults.HIST_MODE  # "Histogram", "ECDF"
    hist_bin_step: float = defaults.HIST_BIN_STEP
    hist_chart_kind: str = defaults.HIST_CHART_KIND  # "Line", "Bar"
    hist_bar_alpha: int = defaults.HIST_BAR_ALPHA
    # 画像を切り替えても保持する plot 設定（grid・log・auto range）
    plot_settings: dict = field(default_factory=lambda: copy.deepcopy(defaults.PLOT_SETTINGS))
    channel_checks: list[bool] = field(default_factory=list)
