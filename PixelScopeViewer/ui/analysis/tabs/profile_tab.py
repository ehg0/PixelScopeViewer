"""profile tab。"""

from collections.abc import Callable

import pyqtgraph as pg
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from PixelScopeViewer.ui.analysis.tabs.common import (
    SPLIT_TITLE_SIZE,
    SplitPlotView,
    StatsTable,
    create_channel_group,
    create_export_group,
    create_plot_widget,
    create_roi_group,
    label_color,
    make_group_box,
    mouse_position_text,
)
from PixelScopeViewer.ui.common import theme

_ORIENTATION_LABELS = {"h": "Horizontal", "v": "Vertical", "d": "Diagonal"}
_METHOD_LABELS = {"mean": "Mean", "std": "Std", "max": "Max", "min": "Min", "p2p": "Peak-to-Peak", "median": "Median"}


def _plot_curves(plot, series: dict, color_by_label: dict[str, tuple[int, int, int]]):
    for label, (xs, ys) in series.items():
        pen = pg.mkPen(color=label_color(label, color_by_label), width=2)
        plot.plot(xs, ys, pen=pen, name=label if label != "I" else "Intensity")


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

        # 左側: plot（編集中ROI・Overlay は prof_widget、Split は split_view）と統計量
        left = QVBoxLayout()
        self.prof_widget = create_plot_widget(
            "Intensity", "Position", on_save_viewbox_state, on_connect_plot_controls, self._on_mouse_over
        )
        self.split_view = SplitPlotView(
            self.prof_widget.getPlotItem(), "Intensity", "Position", self.status_changed.emit
        )
        self.split_area = self.split_view.area
        self.plot_stack = QStackedWidget()
        self.plot_stack.addWidget(self.prof_widget)
        self.plot_stack.addWidget(self.split_view)
        left.addWidget(self.plot_stack, 3)
        # profile は mean などの計算値のため、統計量は常に小数で表示する
        self.stats_table = StatsTable(int_format=False)
        left.addWidget(self.stats_table, 0)
        root.addLayout(left, 1)

        # 右側の control
        right = QVBoxLayout()
        right.setContentsMargins(10, 10, 10, 10)
        right.setSpacing(8)

        self.roi_group, self.roi_mode_combo, self.link_axes_check, self.split_columns_combo = create_roi_group()
        right.addWidget(self.roi_group)

        channels_group, self.channel_scroll, self.channel_list, self.roi_channel_panel = create_channel_group(
            self._on_checkbox_changed
        )
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

    def set_roi_view(self, mode: str):
        """ROI の表示方法（"active" / "overlay" / "split"）に合わせて plot と channel の一覧を切り替える。"""
        self.plot_stack.setCurrentWidget(self.split_view if mode == "split" else self.prof_widget)
        self.channel_list.setVisible(mode == "active")
        self.roi_channel_panel.setVisible(mode != "active")

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
        title_prefix: str = "Profile",
    ):
        """計算済みのデータで profile の plot と統計量の table を更新する。

        Args:
            series: label から (x, y) への dict。
            stats_rows: profile_stats の戻り値。
            orientation: 'h'（水平）または 'v'（垂直）。
            x_mode: 'relative' または 'absolute'。
            method: 'mean', 'std', 'max', 'min', 'p2p', 'median' のいずれか。
            color_by_label: label（C{index} / I）から RGB への dict。
            title_prefix: title の先頭（Overlay では "Profile Overlay (R0,R1)" など）。
        """
        self.prof_widget.clear()
        _plot_curves(self.prof_widget, series, color_by_label)
        self.prof_widget.setTitle(
            f"{title_prefix} - {self._settings_text(orientation, x_mode, method)}",
            color=theme.PLOT_TEXT_COLOR,
            size="12pt",
        )
        self.prof_widget.setLabel("bottom", self._bottom_label(x_mode))
        self.prof_widget.setLabel("left", "Intensity")
        self.stats_table.set_rows(stats_rows, color_by_label)

    def update_split_plots(
        self,
        groups: list[tuple[int, str, str, dict]],
        stats_rows: list[dict],
        x_mode: str,
        color_by_label: dict[str, tuple[int, int, int]],
        link_axes: bool,
        n_cols: int,
    ):
        """登録 ROI ごとの profile を grid に並べて描画し、統計量の table を更新する。

        Args:
            groups: (ROI の id, title, title の色, label から (x, y) への dict) のリスト。
            stats_rows: 全 ROI の統計量の行。
            x_mode: 'relative' または 'absolute'。
            color_by_label: label から RGB への dict。
            link_axes: 全グラフの軸を連動させるか。
            n_cols: grid の列数。
        """
        items = self.split_view.plot_items([g[0] for g in groups], n_cols)
        for item, (_, title, title_color, series) in zip(items, groups, strict=True):
            item.clear()
            _plot_curves(item, series, color_by_label)
            item.setTitle(title, color=title_color, size=SPLIT_TITLE_SIZE)
            item.setLabel("bottom", self._bottom_label(x_mode))
        self.split_area.set_linked(link_axes, [s for g in groups for s in g[3].values()])
        self.stats_table.set_rows(stats_rows, color_by_label)

    @staticmethod
    def _settings_text(orientation: str, x_mode: str, method: str) -> str:
        mode_label = "Absolute" if x_mode == "absolute" else "Relative"
        return f"{_ORIENTATION_LABELS[orientation]} / {mode_label} / {_METHOD_LABELS[method]}"

    @staticmethod
    def _bottom_label(x_mode: str) -> str:
        return "Position" if x_mode == "relative" else "Absolute Position"

    def _on_mouse_over(self, pos):
        self.status_changed.emit(mouse_position_text(self.prof_widget.getPlotItem(), pos))
