from collections.abc import Callable

import numpy as np
import pyqtgraph as pg
from pyqtgraph import PlotWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class HistogramTab(QWidget):
    """Histogram tab UI with pyqtgraph plot, stats table, and controls.

    Parameters
    ----------
    pyqtgraph_available: bool
        Whether pyqtgraph is available. If False, plot widget is None.
    on_save_viewbox_state: Optional[Callable[[object], None]]
        Callback to persist ViewBox state; receives the ViewBox instance.
    on_connect_plot_controls: Optional[Callable[[object], None]]
        Callback to connect PlotItem control signals for persistence; receives PlotItem.
    """

    # ステータスバーに表示したい文字列を送るシグナルを定義
    status_changed = Signal(str)

    def __init__(
        self,
        pyqtgraph_available: bool,
        on_save_viewbox_state: Callable[[object], None] | None = None,
        on_connect_plot_controls: Callable[[object], None] | None = None,
        on_channel_changed: Callable[[list], None] | None = None,
        on_spinbox_changed: Callable[[list], None] | None = None,
        on_spinbox_bar_alpha_changed: Callable[[list], None] | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.hist_widget = None
        self.on_channel_changed = on_channel_changed
        self.on_spinbox_changed = on_spinbox_changed
        self.on_spinbox_bar_alpha_changed = on_spinbox_bar_alpha_changed
        self.channel_checkboxes: list[QCheckBox] = []
        self.MAX_CHANNELS = 8

        root = QHBoxLayout(self)

        left = QVBoxLayout()
        if pyqtgraph_available and PlotWidget is not None:
            self.hist_widget = PlotWidget()
            self.hist_widget.setLabel("left", "Count")
            self.hist_widget.setLabel("bottom", "Intensity")
            self.hist_widget.setBackground("white")
            self.hist_widget.showGrid(x=True, y=True, alpha=0.4)
            try:
                self.hist_widget.getAxis("left").setPen(pg.mkPen(color="#7f8c8d", width=1))
                self.hist_widget.getAxis("bottom").setPen(pg.mkPen(color="#7f8c8d", width=1))
                self.hist_widget.getAxis("left").setTextPen(pg.mkPen(color="#2c3e50"))
                self.hist_widget.getAxis("bottom").setTextPen(pg.mkPen(color="#2c3e50"))
            except Exception:
                pass
            self.hist_widget.setMenuEnabled(True)
            try:
                view_box = self.hist_widget.getViewBox()
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
                    on_connect_plot_controls(self.hist_widget.getPlotItem())
            except Exception:
                pass
            left.addWidget(self.hist_widget, 3)

            # マウスオーバーしたら、ステータスバーにマウス位置の値を表示
            self.hist_widget.scene().sigMouseMoved.connect(self._on_mouse_over)

        # Stats table
        self.stats_table = QTableWidget()
        stats_headers = ["ch", "Mean", "Std", "Median", "Min", "Max", "Fano"]
        self.stats_table.setColumnCount(len(stats_headers))
        self.stats_table.setHorizontalHeaderLabels(stats_headers)
        self.stats_table.setRowCount(0)
        self.stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.stats_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.stats_table.setSelectionBehavior(QTableWidget.SelectItems)
        # Allow more rows; enable scrolling rather than clipping
        self.stats_table.setMaximumHeight(240)
        self.stats_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        total_w = 600
        ch_w = 120
        other_w = max(60, (total_w - ch_w) // (self.stats_table.columnCount() - 1))
        header = self.stats_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Fixed)
        self.stats_table.setColumnWidth(0, ch_w)
        for c in range(1, self.stats_table.columnCount()):
            self.stats_table.setColumnWidth(c, other_w)
        self.stats_table.setFixedWidth(ch_w + other_w * (self.stats_table.columnCount() - 1) + 2)
        self.stats_table.setStyleSheet("QTableWidget { font-size: 10pt; }")
        self.stats_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.stats_table.verticalHeader().setVisible(False)
        left.addWidget(self.stats_table, 0)

        root.addLayout(left, 1)

        # Right column with grouped controls
        right = QVBoxLayout()
        right.setContentsMargins(10, 10, 10, 10)
        right.setSpacing(8)

        channels_group = QGroupBox("Channels")
        channels_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin: 3px 0px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            """)
        channels_layout = QVBoxLayout(channels_group)
        channels_layout.setContentsMargins(8, 5, 8, 8)

        # Scroll area for checkboxes
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setMinimumHeight(120)  # Ensure 4 channels visible without scrolling
        scroll.setMaximumHeight(300)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(2, 2, 2, 2)
        scroll_layout.setSpacing(3)

        # Create checkboxes for channels
        for i in range(self.MAX_CHANNELS):
            cb = QCheckBox(f"C{i}")
            cb.setVisible(False)  # Initially hidden
            cb.stateChanged.connect(self._on_checkbox_changed)
            scroll_layout.addWidget(cb)
            self.channel_checkboxes.append(cb)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        channels_layout.addWidget(scroll)
        right.addWidget(channels_group)

        config_group = QGroupBox("Histgram config")
        config_group.setStyleSheet(channels_group.styleSheet())
        config_layout = QVBoxLayout(config_group)
        config_layout.setContentsMargins(8, 5, 8, 8)
        self.config_mode_btn = QPushButton("Histogram")
        self.config_mode_btn.setMaximumWidth(100)
        config_layout.addWidget(self.config_mode_btn)
        self.chart_kind_combo = QComboBox()
        self.chart_kind_combo.addItems(["Line", "Bar"])
        self.chart_kind_combo.setMinimumWidth(100)
        config_layout.addWidget(self.chart_kind_combo)
        label = QLabel("color alpha:")
        config_layout.addWidget(label)
        self.bar_alpha_spin_box_init = 120
        self.bar_alpha_spin_box = QSpinBox()
        self.bar_alpha_spin_box.setRange(0, 255)  # 入力できる最小値・最大値
        self.bar_alpha_spin_box.setSingleStep(10)  # 矢印を押したときの増減幅
        self.bar_alpha_spin_box.setValue(self.bar_alpha_spin_box_init)  # 初期値
        self.bar_alpha_spin_box.valueChanged.connect(self._on_spinbox_bar_alpha_changed)
        config_layout.addWidget(self.bar_alpha_spin_box)
        bis_step_layout = QHBoxLayout()
        label = QLabel("bin step:")
        self.config_reset_btn = QPushButton("Reset")
        self.config_reset_btn.setMaximumWidth(60)
        bis_step_layout.addWidget(label)
        bis_step_layout.addWidget(self.config_reset_btn)
        config_layout.addLayout(bis_step_layout)
        self.bin_step_spin_box_init = 1.0
        self.bin_step_spin_box = QDoubleSpinBox()
        self.bin_step_spin_box.setRange(0.001, 100.0)  # 入力できる最小値・最大値
        self.bin_step_spin_box.setSingleStep(0.1)  # 矢印を押したときの増減幅
        self.bin_step_spin_box.setDecimals(3)  # 小数点以下の桁数
        self.bin_step_spin_box.setValue(self.bin_step_spin_box_init)  # 初期値
        self.bin_step_spin_box.valueChanged.connect(self._on_spinbox_changed)
        config_layout.addWidget(self.bin_step_spin_box)
        self.setLayout(config_layout)
        right.addWidget(config_group)

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
        """Called when any checkbox changes state."""
        if self.on_channel_changed:
            checks = [cb.isChecked() for cb in self.channel_checkboxes if cb.isVisible()]
            self.on_channel_changed(checks)

    def _on_spinbox_changed(self, value):
        self.on_spinbox_changed(value)

    def _on_spinbox_bar_alpha_changed(self, value):
        self.on_spinbox_bar_alpha_changed(value)

    def update_channel_checkboxes(self, nch: int, checks: list[bool], channel_colors: list | None = None):
        """Update channel checkboxes visibility, state, and colors.

        Parameters
        ----------
        nch: int
            Number of channels
        checks: list[bool]
            Checkbox states
        channel_colors: list, optional
            List of QColor objects for channel colors
        """
        for i in range(self.MAX_CHANNELS):
            cb = self.channel_checkboxes[i]
            if i < nch:
                cb.setVisible(True)
                # Block signals while updating to prevent recursive updates
                cb.blockSignals(True)
                cb.setChecked(checks[i] if i < len(checks) else True)
                cb.blockSignals(False)
                cb.setEnabled(nch > 1)  # Disable if only 1 channel

                # Add color swatch icon
                if channel_colors and i < len(channel_colors):
                    color = channel_colors[i]
                    if hasattr(color, "name"):
                        pix = QPixmap(14, 14)
                        pix.fill(color)
                        cb.setIcon(pix)
                        cb.setIconSize(pix.size())
                    else:
                        cb.setIcon(QPixmap())  # Clear icon
                else:
                    cb.setIcon(QPixmap())  # Clear icon
            else:
                cb.setVisible(False)

    def update(
        self,
        series: dict,
        stats_rows: list[dict],
        apply_log: bool = False,
        is_integer_type: bool = False,
        channel_colors: list | None = None,
        chart_kind: str = "Line",
        bar_alpha: int = 120,
    ):
        """Update histogram plot and statistics table with pre-computed data.

        Parameters
        ----------
        series: dict
            Mapping of label -> (xs, ys) for histogram data
        stats_rows: list[dict]
            List of dicts with keys: ch, mean, std, median, min, max, is_int
        apply_log: bool
            If True, apply log10(y+1) transform to histogram counts
        is_integer_type: bool
            If True, format x-axis with integer ticks for integer data types
        channel_colors: list, optional
            List of QColor objects for channel colors from viewer
        """
        if self.hist_widget is None:
            return

        # Clear and plot histogram
        self.hist_widget.clear()

        # Resolve overlay color map if present (tiling comparison)
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

        # Helper to resolve color per label
        def _color_for_label(label: str, alpha: int = 255) -> QColor:
            # 1. Overlay mapping
            rgb = overlay_map.get(label)
            if rgb:
                return QColor(rgb[0], rgb[1], rgb[2], alpha)

            # 2. Intensity
            if label == "I":
                return QColor(0, 0, 0, alpha)

            # 3. Channel index 抽出
            ch_index = None
            if label.startswith("C") and label[1:].isdigit():
                ch_index = int(label[1:])
            else:
                parts = label.replace("_", " ").split()
                for p in parts:
                    if p.startswith("C") and p[1:].isdigit():
                        ch_index = int(p[1:])
                        break

            # 4. Color 決定（文字列または QColor オブジェクト）
            color_val = None
            if ch_index is not None and channel_colors and 0 <= ch_index < len(channel_colors):
                color_val = channel_colors[ch_index]

            if color_val is None:
                fallback = ["#ff0000", "#00c800", "#0066ff", "#7f7f7f"]
                if ch_index is not None and ch_index < len(fallback):
                    color_val = fallback[ch_index]
                else:
                    color_val = "#7f8c8d"

            # QColor に変換して alpha を設定
            qcolor = QColor(color_val)
            # 表示カラーがグレースケールの時はグラフ線色を黒にする
            if qcolor.red() == qcolor.green() == qcolor.blue():
                qcolor.setRgb(0, 0, 0)
            qcolor.setAlpha(alpha)

            return qcolor

        for _, (label, (xs, ys)) in enumerate(series.items()):
            yplot = np.array(ys, dtype=float)
            if apply_log:
                # 0のデータを0.1に置換（log10(0.1) = -1 として最下部に張り付く）
                yplot[yplot == 0] = 0.1
                self.hist_widget.setLimits(yMin=-1)

            if chart_kind == "Line":
                pen = pg.mkPen(color=_color_for_label(label, alpha=255), width=2)
                self.hist_widget.plot(xs, yplot, pen=pen, name=label if label != "I" else "Intensity")

            if chart_kind == "Bar":
                pen = pg.mkPen(color=_color_for_label(label, alpha=bar_alpha), width=2)
                item = pg.BarGraphItem(
                    x=xs, height=yplot, width=self.bin_step_spin_box.value(), brush=pen.color(), pen=None, name=label
                )
                self.hist_widget.addItem(item)

        # Set title
        self.hist_widget.setTitle(f"Intensity {self.config_mode_btn.text()}", color="#2c3e50", size="12pt")

        # Configure x-axis for integer types
        if is_integer_type and pg is not None:
            try:
                axis = self.hist_widget.getAxis("bottom")
                # Force integer ticks for integer data types
                axis.setStyle(tickTextOffset=10)
            except Exception:
                pass  # If axis configuration fails, just use default

        # Update statistics table
        self._populate_stats_table(stats_rows)

    def _populate_stats_table(self, rows: list[dict]):
        """Populate stats table from computed statistics."""
        # Locate parent dialog (has overlay_color_map or channel_color_map) safely
        dlg = self
        color_map = {}
        assign_colors = None
        visited = set()
        while dlg is not None and id(dlg) not in visited:
            visited.add(id(dlg))
            # Check for overlay_color_map (tiling comparison) or channel_color_map (normal analysis)
            if hasattr(dlg, "overlay_color_map"):
                color_map = getattr(dlg, "overlay_color_map", {}) or {}
                assign_colors = getattr(dlg, "_assign_overlay_colors", None)
                break
            elif hasattr(dlg, "channel_color_map"):
                color_map = getattr(dlg, "channel_color_map", {}) or {}
                break
            # Obtain parent only if callable
            parent_attr = getattr(dlg, "parent", None)
            if callable(parent_attr):
                try:
                    dlg = parent_attr()
                except Exception:
                    dlg = None
            else:
                dlg = None

        self.stats_table.setRowCount(len(rows))
        for row_idx, r in enumerate(rows):
            ch_text = r["ch"]
            ch_item = QTableWidgetItem(ch_text)
            # Color swatch based on curve_label mapping or direct channel label
            curve_label = r.get("curve_label")
            rgb = color_map.get(curve_label) if (curve_label and color_map) else None

            # For normal analysis dialog, try direct channel numeric or symbolic label
            if rgb is None:
                if ch_text in color_map:
                    rgb = color_map.get(ch_text)
                else:
                    symbolic = f"C{ch_text}"  # map digits -> C{index}
                    if symbolic in color_map:
                        rgb = color_map.get(symbolic)

            if rgb is None:
                # Fallback: support underscore pattern 'T{n}_C{k}' for tiling comparison
                tile_num = None
                channel_code = None
                if "_" in ch_text:
                    tpart, cpart = ch_text.split("_", 1)
                    if tpart.startswith("T") and cpart.startswith("C") and cpart[1:].isdigit():
                        tile_num = tpart[1:]
                        channel_code = cpart
                else:
                    # legacy space separated pattern
                    parts = ch_text.split()
                    if len(parts) == 2 and parts[0].startswith("T"):
                        tile_num = parts[0][1:]
                        channel_code = parts[1]
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
            self.stats_table.setItem(row_idx, 0, ch_item)

            mi = QTableWidgetItem(f"{r['mean']:.4f}")
            mi.setTextAlignment(Qt.AlignCenter)
            si = QTableWidgetItem(f"{r['std']:.4f}")
            si.setTextAlignment(Qt.AlignCenter)
            mdi = QTableWidgetItem(f"{int(r['median'])}" if r["is_int"] else f"{r['median']:.4f}")
            mdi.setTextAlignment(Qt.AlignCenter)
            mini = QTableWidgetItem(f"{int(r['min'])}" if r["is_int"] else f"{r['min']:.4f}")
            mini.setTextAlignment(Qt.AlignCenter)
            maxi = QTableWidgetItem(f"{int(r['max'])}" if r["is_int"] else f"{r['max']:.4f}")
            maxi.setTextAlignment(Qt.AlignCenter)
            fanoi = QTableWidgetItem(f"{int(r['fano'])}" if r["is_int"] else f"{r['fano']:.4f}")
            fanoi.setTextAlignment(Qt.AlignCenter)
            self.stats_table.setItem(row_idx, 1, mi)
            self.stats_table.setItem(row_idx, 2, si)
            self.stats_table.setItem(row_idx, 3, mdi)
            self.stats_table.setItem(row_idx, 4, mini)
            self.stats_table.setItem(row_idx, 5, maxi)
            self.stats_table.setItem(row_idx, 6, fanoi)
            for col in range(1, 6):
                item = self.stats_table.item(row_idx, col)
                if item is not None:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)

    def _on_mouse_over(self, pos):
        plot_item = self.hist_widget.getPlotItem()

        if plot_item.sceneBoundingRect().contains(pos):
            mouse_point = plot_item.vb.mapSceneToView(pos)
            x_val, y_val = mouse_point.x(), mouse_point.y()

            # Logモード判定&逆変換
            vb_state = plot_item.vb.getState()
            is_log_x = vb_state.get("logMode", [False, False])[0]
            is_log_y = vb_state.get("logMode", [False, False])[1]

            # X軸の逆変換
            if is_log_x:
                x_val = 10**x_val

            # Y軸の逆変換
            if is_log_y:
                y_val = 10**y_val
            self.status_changed.emit(f"X: {x_val:.2f}, Y: {y_val:.2f}")

        else:
            # 範囲外の場合は空文字を送信
            self.status_changed.emit("")
