"""profile tab。"""

from collections.abc import Callable

import pyqtgraph as pg
from pyqtgraph import PlotWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from PixelScopeViewer.ui.common import defaults, theme


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
        self.channel_checkboxes: list[QCheckBox] = []

        root = QHBoxLayout(self)

        # 左側: plot と統計量
        left = QVBoxLayout()

        self.prof_widget = PlotWidget()
        self.prof_widget.setLabel("left", "Intensity")
        self.prof_widget.setLabel("bottom", "Position")
        self.prof_widget.setBackground(theme.PLOT_BACKGROUND)
        self.prof_widget.showGrid(x=True, y=True, alpha=0.4)
        try:
            self.prof_widget.getAxis("left").setPen(pg.mkPen(color=theme.PLOT_AXIS_COLOR, width=1))
            self.prof_widget.getAxis("bottom").setPen(pg.mkPen(color=theme.PLOT_AXIS_COLOR, width=1))
            self.prof_widget.getAxis("left").setTextPen(pg.mkPen(color=theme.PLOT_TEXT_COLOR))
            self.prof_widget.getAxis("bottom").setTextPen(pg.mkPen(color=theme.PLOT_TEXT_COLOR))
        except Exception:
            pass
        self.prof_widget.setMenuEnabled(True)
        try:
            view_box = self.prof_widget.getViewBox()
            view_box.setMouseEnabled(x=False, y=False)
            if on_save_viewbox_state is not None:
                try:
                    view_box.sigStateChanged.connect(lambda vb: on_save_viewbox_state(vb))
                    on_save_viewbox_state(view_box)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if on_connect_plot_controls is not None:
                on_connect_plot_controls(self.prof_widget.getPlotItem())
        except Exception:
            pass
        left.addWidget(self.prof_widget, 3)

        # マウス位置の値を status bar に表示する
        self.prof_widget.scene().sigMouseMoved.connect(self._on_mouse_over)

        self.prof_stats_table = QTableWidget()
        stats_headers = ["ch", "Mean", "Std", "Median", "Min", "Max", "Fano"]
        self.prof_stats_table.setColumnCount(len(stats_headers))
        self.prof_stats_table.setHorizontalHeaderLabels(stats_headers)
        self.prof_stats_table.setRowCount(0)
        self.prof_stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.prof_stats_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.prof_stats_table.setSelectionBehavior(QTableWidget.SelectItems)
        # 行が多い場合は切り詰めずに scroll させる
        self.prof_stats_table.setMaximumHeight(240)
        self.prof_stats_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        total_w = 600
        ch_w = 120
        other_w = max(60, (total_w - ch_w) // (self.prof_stats_table.columnCount() - 1))
        header = self.prof_stats_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Fixed)
        self.prof_stats_table.setColumnWidth(0, ch_w)
        for c in range(1, self.prof_stats_table.columnCount()):
            self.prof_stats_table.setColumnWidth(c, other_w)
        self.prof_stats_table.setFixedWidth(ch_w + other_w * (self.prof_stats_table.columnCount() - 1) + 2)
        self.prof_stats_table.setStyleSheet("QTableWidget { font-size: 10pt; }")
        self.prof_stats_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.prof_stats_table.verticalHeader().setVisible(False)
        left.addWidget(self.prof_stats_table, 0)

        root.addLayout(left, 1)

        # 右側の control
        right = QVBoxLayout()
        right.setContentsMargins(10, 10, 10, 10)
        right.setSpacing(8)

        channels_group = QGroupBox("Channels")
        channels_group.setStyleSheet(theme.GROUP_BOX_STYLESHEET)
        channels_layout = QVBoxLayout(channels_group)
        channels_layout.setContentsMargins(8, 5, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(120)  # 4 channel までは scroll なしで表示する
        scroll.setMaximumHeight(300)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(2, 2, 2, 2)
        scroll_layout.setSpacing(3)

        for i in range(defaults.MAX_CHANNEL_CHECKBOXES):
            cb = QCheckBox(f"C{i}")
            cb.setVisible(False)
            cb.stateChanged.connect(self._on_checkbox_changed)
            scroll_layout.addWidget(cb)
            self.channel_checkboxes.append(cb)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        channels_layout.addWidget(scroll)
        right.addWidget(channels_group)

        display_group = QGroupBox("Display Settings")
        display_group.setStyleSheet(channels_group.styleSheet())
        display_layout = QVBoxLayout(display_group)
        display_layout.setContentsMargins(8, 5, 8, 8)
        self.orientation_btn = QPushButton("Horizontal")
        self.orientation_btn.setMinimumWidth(100)
        display_layout.addWidget(self.orientation_btn)
        self.xmode_btn = QPushButton("Relative")
        self.xmode_btn.setMinimumWidth(100)
        display_layout.addWidget(self.xmode_btn)
        self.compute_method_combo = QComboBox()
        self.compute_method_combo.addItems(["mean", "std", "max", "min", "p2p", "median"])
        self.compute_method_combo.setMinimumWidth(100)
        display_layout.addWidget(self.compute_method_combo)
        right.addWidget(display_group)

        export_group = QGroupBox("Export")
        export_group.setStyleSheet(channels_group.styleSheet())
        export_layout = QVBoxLayout(export_group)
        export_layout.setContentsMargins(8, 5, 8, 8)
        self.copy_btn = QPushButton("Copy data")
        self.copy_btn.setMinimumWidth(100)
        export_layout.addWidget(self.copy_btn)
        self.copy_stats_btn = QPushButton("Copy stats")
        self.copy_stats_btn.setMinimumWidth(100)
        export_layout.addWidget(self.copy_stats_btn)
        self.get_all_plane_data = QCheckBox("Target: All plane")
        self.get_all_plane_data.setMinimumWidth(100)
        export_layout.addWidget(self.get_all_plane_data)
        right.addWidget(export_group)

        right.addStretch(1)
        root.addLayout(right)

    def _on_checkbox_changed(self):
        if self.on_channel_changed:
            checks = [cb.isChecked() for cb in self.channel_checkboxes if cb.isVisible()]
            self.on_channel_changed(checks)

    def update_channel_checkboxes(self, nch: int, checks: list[bool], channel_colors: list | None = None):
        """channel の checkbox の表示・状態・色を更新する。

        Args:
            nch: channel 数。
            checks: checkbox の状態。
            channel_colors: channel ごとの QColor。
        """
        for i in range(defaults.MAX_CHANNEL_CHECKBOXES):
            cb = self.channel_checkboxes[i]
            if i < nch:
                cb.setVisible(True)
                # 更新中に signal が再帰的に発火しないようにする
                cb.blockSignals(True)
                cb.setChecked(checks[i] if i < len(checks) else True)
                cb.blockSignals(False)
                cb.setEnabled(nch > 1)

                # 色見本の icon
                if channel_colors and i < len(channel_colors):
                    color = channel_colors[i]
                    if hasattr(color, "name"):
                        pix = QPixmap(14, 14)
                        pix.fill(color)
                        cb.setIcon(pix)
                        cb.setIconSize(pix.size())
                    else:
                        cb.setIcon(QPixmap())
                else:
                    cb.setIcon(QPixmap())
            else:
                cb.setVisible(False)

    def update_plot(
        self,
        series: dict,
        stats_rows: list[dict],
        orientation: str,
        x_mode: str,
        method: str,
        channel_colors: list | None = None,
    ):
        """計算済みのデータで profile の plot と統計量の table を更新する。

        Args:
            series: label から (x, y) への dict。
            stats_rows: profile_stats の戻り値。
            orientation: 'h'（水平）または 'v'（垂直）。
            x_mode: 'relative' または 'absolute'。
            method: 'mean', 'std', 'max', 'min', 'p2p', 'median' のいずれか。
            channel_colors: channel ごとの QColor。
        """
        self.prof_widget.clear()

        # 複数画像比較では親 dialog の overlay_color_map を使う
        overlay_map = {}
        dlg = self
        visited = set()
        while dlg is not None and id(dlg) not in visited:
            visited.add(id(dlg))
            if hasattr(dlg, "overlay_color_map"):
                overlay_map = getattr(dlg, "overlay_color_map", {}) or {}
                break
            parent_attr = getattr(dlg, "parent", None)
            if callable(parent_attr):
                try:
                    dlg = parent_attr()
                except Exception:
                    dlg = None
            else:
                dlg = None

        def _color_for_label(label: str) -> str:
            rgb = overlay_map.get(label)
            if rgb:
                # grayscale の色は見やすさのため黒で描画する
                if rgb[0] == rgb[1] == rgb[2]:
                    return theme.PLOT_INTENSITY_COLOR
                return f"rgb({rgb[0]},{rgb[1]},{rgb[2]})"
            # Intensity は常に黒
            if label == "I":
                return theme.PLOT_INTENSITY_COLOR
            ch_index = None
            if label.startswith("C") and label[1:].isdigit():
                ch_index = int(label[1:])
            else:
                parts = label.replace("_", " ").split()
                for p in parts:
                    if p.startswith("C") and p[1:].isdigit():
                        ch_index = int(p[1:])
                        break
            if ch_index is not None and channel_colors and 0 <= ch_index < len(channel_colors):
                c = channel_colors[ch_index]
                # grayscale の色は見やすさのため黒で描画する
                if c.red() == c.green() == c.blue():
                    return theme.PLOT_INTENSITY_COLOR
                return c.name() if hasattr(c, "name") else theme.PLOT_MUTED_COLOR
            fallback = theme.PLOT_FALLBACK_CHANNEL_COLORS
            if ch_index is not None and ch_index < len(fallback):
                return fallback[ch_index]
            return theme.PLOT_MUTED_COLOR

        for _, (label, (xs, ys)) in enumerate(series.items()):
            pen = pg.mkPen(color=_color_for_label(label), width=2)
            self.prof_widget.plot(xs, ys, pen=pen, name=label if label != "I" else "Intensity")

        orientation_label = {"h": "Horizontal", "v": "Vertical", "d": "Diagonal"}[orientation]
        mode_label = "Absolute" if x_mode == "absolute" else "Relative"
        method_label = {
            "mean": "Mean",
            "std": "Std",
            "max": "Max",
            "min": "Min",
            "p2p": "Peak-to-Peak",
            "median": "Median",
        }[method]
        self.prof_widget.setTitle(
            f"Profile - {orientation_label} / {mode_label} / {method_label}", color=theme.PLOT_TEXT_COLOR, size="12pt"
        )
        self.prof_widget.setLabel("bottom", "Position" if x_mode == "relative" else "Absolute Position")
        self.prof_widget.setLabel("left", "Intensity")

        self._populate_stats_table(stats_rows)

    def _populate_stats_table(self, rows: list[dict]):
        """統計量の table を更新する。"""
        dlg = self
        color_map = {}
        assign_colors = None
        visited = set()
        while dlg is not None and id(dlg) not in visited:
            visited.add(id(dlg))
            # 複数画像比較の overlay_color_map または通常の channel_color_map を探す
            if hasattr(dlg, "overlay_color_map"):
                color_map = getattr(dlg, "overlay_color_map", {}) or {}
                assign_colors = getattr(dlg, "_assign_overlay_colors", None)
                break
            elif hasattr(dlg, "channel_color_map"):
                color_map = getattr(dlg, "channel_color_map", {}) or {}
                break
            parent_attr = getattr(dlg, "parent", None)
            if callable(parent_attr):
                try:
                    dlg = parent_attr()
                except Exception:
                    dlg = None
            else:
                dlg = None

        self.prof_stats_table.setRowCount(len(rows))
        for row_idx, r in enumerate(rows):
            ch_text = r["ch"]
            ch_item = QTableWidgetItem(ch_text)
            curve_label = r.get("curve_label")
            rgb = color_map.get(curve_label) if (curve_label and color_map) else None
            if rgb is None:
                if ch_text in color_map:
                    rgb = color_map.get(ch_text)
                else:
                    symbolic = f"C{ch_text}"
                    if symbolic in color_map:
                        rgb = color_map.get(symbolic)

            if rgb is None:
                # 複数画像比較の 'T{n}_C{k}' 形式に対応する
                ch_text = r.get("ch", "")
                tile_num = None
                channel_code = None
                if "_" in ch_text:
                    tpart, cpart = ch_text.split("_", 1)
                    if tpart.startswith("T") and cpart.startswith("C") and cpart[1:].isdigit():
                        tile_num = tpart[1:]
                        channel_code = cpart
                if tile_num is not None and channel_code is not None and color_map is not None:
                    derived = f"Tile {tile_num} {channel_code}"
                    curve_label = derived
                    rgb = color_map.get(derived)
                    if rgb is None and assign_colors is not None:
                        try:
                            assign_colors([derived])
                            rgb = getattr(dlg, "overlay_color_map", {}).get(derived)
                        except Exception:
                            rgb = None
            if rgb:
                pix = QPixmap(12, 12)
                pix.fill(QColor(*rgb))
                ch_item.setData(Qt.DecorationRole, pix)
            ch_item.setFlags(ch_item.flags() & ~Qt.ItemIsEditable)
            ch_item.setTextAlignment(Qt.AlignCenter)
            self.prof_stats_table.setItem(row_idx, 0, ch_item)

            mi = QTableWidgetItem(f"{r['mean']:.4f}")
            mi.setTextAlignment(Qt.AlignCenter)
            si = QTableWidgetItem(f"{r['std']:.4f}")
            si.setTextAlignment(Qt.AlignCenter)
            mdi = QTableWidgetItem(f"{r['median']:.4f}")
            mdi.setTextAlignment(Qt.AlignCenter)
            mini = QTableWidgetItem(f"{r['min']:.4f}")
            mini.setTextAlignment(Qt.AlignCenter)
            maxi = QTableWidgetItem(f"{r['max']:.4f}")
            maxi.setTextAlignment(Qt.AlignCenter)
            fanoi = QTableWidgetItem(f"{r['fano']:.4f}")
            fanoi.setTextAlignment(Qt.AlignCenter)
            self.prof_stats_table.setItem(row_idx, 1, mi)
            self.prof_stats_table.setItem(row_idx, 2, si)
            self.prof_stats_table.setItem(row_idx, 3, mdi)
            self.prof_stats_table.setItem(row_idx, 4, mini)
            self.prof_stats_table.setItem(row_idx, 5, maxi)
            self.prof_stats_table.setItem(row_idx, 6, fanoi)
            for col in range(1, 6):
                item = self.prof_stats_table.item(row_idx, col)
                if item is not None:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)

    def _on_mouse_over(self, pos):
        plot_item = self.prof_widget.getPlotItem()

        if plot_item.sceneBoundingRect().contains(pos):
            mouse_point = plot_item.vb.mapSceneToView(pos)
            x_val, y_val = mouse_point.x(), mouse_point.y()

            # log 表示の場合は元の値に戻す
            vb_state = plot_item.vb.getState()
            is_log_x = vb_state.get("logMode", [False, False])[0]
            is_log_y = vb_state.get("logMode", [False, False])[1]

            if is_log_x:
                x_val = 10**x_val

            if is_log_y:
                y_val = 10**y_val
            self.status_changed.emit(f"X: {x_val:.2f}, Y: {y_val:.2f}")

        else:
            self.status_changed.emit("")
