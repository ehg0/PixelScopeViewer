"""profile tab。"""

from collections.abc import Callable

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from PixelScopeViewer.ui.analysis.tabs.common import (
    StatsTable,
    create_channel_group,
    create_export_group,
    create_plot_widget,
    label_color,
    make_group_box,
    mouse_position_text,
)
from PixelScopeViewer.ui.common import theme

_ORIENTATION_LABELS = {"h": "Horizontal", "v": "Vertical", "d": "Diagonal"}
_METHOD_LABELS = {"mean": "Mean", "std": "Std", "max": "Max", "min": "Min", "p2p": "Peak-to-Peak", "median": "Median"}


class ProfileTab(QWidget):
    """profile の plot、統計量の table、設定 control を持つ tab。

    Args:
        on_save_viewbox_state: ViewBox の状態を保存する callback。
        on_connect_plot_controls: PlotItem の control を接続する callback。
        on_channel_changed: channel の表示 ON/OFF 変更時の callback。
        parent: 親 widget。
    """

    # status bar に表示する文字列
    status_changed = Signal(str)

    def __init__(
        self,
        on_save_viewbox_state: Callable[[object], None] | None = None,
        on_connect_plot_controls: Callable[[object], None] | None = None,
        on_channel_changed: Callable[[list], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.on_channel_changed = on_channel_changed

        root = QHBoxLayout(self)

        # 左側: plot と統計量
        left = QVBoxLayout()
        self.prof_widget = create_plot_widget(
            "Intensity", "Position", on_save_viewbox_state, on_connect_plot_controls, self._on_mouse_over
        )
        left.addWidget(self.prof_widget, 3)
        # profile は mean などの計算値のため、統計量は常に小数で表示する
        self.stats_table = StatsTable(int_format=False)
        left.addWidget(self.stats_table, 0)
        root.addLayout(left, 1)

        # 右側の control
        right = QVBoxLayout()
        right.setContentsMargins(10, 10, 10, 10)
        right.setSpacing(8)

        channels_group, self.channel_list = create_channel_group(self._on_checkbox_changed)
        right.addWidget(channels_group)

        display_group, display_layout = make_group_box("Display Settings")
        self.orientation_btn = QPushButton("Horizontal")
        self.xmode_btn = QPushButton("Relative")
        self.compute_method_combo = QComboBox()
        self.compute_method_combo.addItems(list(_METHOD_LABELS))
        for w in (self.orientation_btn, self.xmode_btn, self.compute_method_combo):
            w.setMinimumWidth(100)
            display_layout.addWidget(w)
        right.addWidget(display_group)

        export_group, self.copy_btn, self.copy_stats_btn, self.get_all_plane_data = create_export_group()
        right.addWidget(export_group)

        right.addStretch(1)
        root.addLayout(right)

    def _on_checkbox_changed(self, checks: list[bool]):
        if self.on_channel_changed:
            self.on_channel_changed(checks)

    def update_channel_checkboxes(self, nch: int, checks: list[bool], channel_colors: list | None = None):
        """channel の行（checkbox・label・色ボタン）を更新する。"""
        self.channel_list.set_channels([f"C{i}" for i in range(nch)], checks, channel_colors or [])

    def update_plot(
        self,
        series: dict,
        stats_rows: list[dict],
        orientation: str,
        x_mode: str,
        method: str,
        color_by_label: dict[str, tuple[int, int, int]],
    ):
        """計算済みのデータで profile の plot と統計量の table を更新する。

        Args:
            series: label から (x, y) への dict。
            stats_rows: profile_stats の戻り値。
            orientation: 'h'（水平）または 'v'（垂直）。
            x_mode: 'relative' または 'absolute'。
            method: 'mean', 'std', 'max', 'min', 'p2p', 'median' のいずれか。
            color_by_label: label（C{index} / I）から RGB への dict。
        """
        self.prof_widget.clear()
        for label, (xs, ys) in series.items():
            pen = pg.mkPen(color=label_color(label, color_by_label), width=2)
            self.prof_widget.plot(xs, ys, pen=pen, name=label if label != "I" else "Intensity")

        mode_label = "Absolute" if x_mode == "absolute" else "Relative"
        self.prof_widget.setTitle(
            f"Profile - {_ORIENTATION_LABELS[orientation]} / {mode_label} / {_METHOD_LABELS[method]}",
            color=theme.PLOT_TEXT_COLOR,
            size="12pt",
        )
        self.prof_widget.setLabel("bottom", "Position" if x_mode == "relative" else "Absolute Position")
        self.prof_widget.setLabel("left", "Intensity")
        self.stats_table.set_rows(stats_rows, color_by_label)

    def _on_mouse_over(self, pos):
        self.status_changed.emit(mouse_position_text(self.prof_widget, pos))
