from typing import Callable, Optional

from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QTableWidget,
    QHeaderView,
    QGroupBox,
)
from PySide6.QtCore import Qt

try:
    import pyqtgraph as pg
    from pyqtgraph import PlotWidget
except Exception:  # pragma: no cover - optional dependency
    pg = None
    PlotWidget = None


class ProfileTab(QWidget):
    """Profile tab UI with pyqtgraph plot, stats table, and controls.

    Parameters
    ----------
    pyqtgraph_available: bool
        Whether pyqtgraph is available. If False, plot widget is None.
    on_save_viewbox_state: Optional[Callable[[object], None]]
        Callback to persist ViewBox state; receives the ViewBox instance.
    on_connect_plot_controls: Optional[Callable[[object], None]]
        Callback to connect PlotItem control signals for persistence; receives PlotItem.
    """

    def __init__(
        self,
        pyqtgraph_available: bool,
        on_save_viewbox_state: Optional[Callable[[object], None]] = None,
        on_connect_plot_controls: Optional[Callable[[object], None]] = None,
        parent=None,
    ):
        super().__init__(parent)

        self.prof_widget = None

        root = QHBoxLayout(self)

        # Left side: plot + stats vertically
        left = QVBoxLayout()

        if pyqtgraph_available and PlotWidget is not None:
            self.prof_widget = PlotWidget()
            self.prof_widget.setLabel("left", "Intensity")
            self.prof_widget.setLabel("bottom", "Position")
            self.prof_widget.setBackground("white")
            self.prof_widget.showGrid(x=True, y=True, alpha=0.4)
            try:
                self.prof_widget.getAxis("left").setPen(pg.mkPen(color="#7f8c8d", width=1))
                self.prof_widget.getAxis("bottom").setPen(pg.mkPen(color="#7f8c8d", width=1))
                self.prof_widget.getAxis("left").setTextPen(pg.mkPen(color="#2c3e50"))
                self.prof_widget.getAxis("bottom").setTextPen(pg.mkPen(color="#2c3e50"))
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

        # Stats table
        self.prof_stats_table = QTableWidget()
        stats_headers = ["ch", "Mean", "Std", "Median", "Min", "Max"]
        self.prof_stats_table.setColumnCount(len(stats_headers))
        self.prof_stats_table.setHorizontalHeaderLabels(stats_headers)
        self.prof_stats_table.setRowCount(0)
        self.prof_stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.prof_stats_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.prof_stats_table.setSelectionBehavior(QTableWidget.SelectItems)
        # Allow more rows; enable scrolling rather than clipping
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

        # Right column with grouped controls
        right = QVBoxLayout()
        right.setContentsMargins(10, 10, 10, 10)
        right.setSpacing(8)

        channels_group = QGroupBox("Channels")
        channels_group.setStyleSheet(
            """
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
            """
        )
        channels_layout = QVBoxLayout(channels_group)
        channels_layout.setContentsMargins(8, 5, 8, 8)
        self.channels_btn = QPushButton("Configure...")
        self.channels_btn.setMinimumWidth(100)
        channels_layout.addWidget(self.channels_btn)
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
        right.addWidget(export_group)

        right.addStretch(1)
        root.addLayout(right)

    def update(self, series: dict, stats_rows: list[dict], orientation: str, x_mode: str, channel_colors: list = None):
        """Update profile plot and statistics table with pre-computed data.

        Parameters
        ----------
        series: dict
            Mapping of label -> (xs, ys) for profile data
        stats_rows: list[dict]
            List of dicts with keys: ch, mean, std, median, min, max, is_int
        orientation: str
            'h', 'v', or 'd' for horizontal/vertical/diagonal
        x_mode: str
            'relative' or 'absolute' for x-axis mode
        channel_colors: list, optional
            List of QColor objects for channel colors from viewer
        """
        if self.prof_widget is None:
            return

        # Clear and plot profile
        self.prof_widget.clear()

        # Determine number of channels from series data
        # If series has only 1 entry or all entries are 'I' (Intensity), treat as grayscale
        num_channels = len(series)
        is_grayscale = num_channels == 1 or all(label == "I" for label in series.keys())

        # Get colors based on channel count
        if is_grayscale:
            # Single channel: use black
            colors = ["#000000"]
        elif channel_colors and len(channel_colors) > 0:
            # Multi-channel: use viewer's channel colors
            colors = [c.name() if hasattr(c, "name") else "#7f8c8d" for c in channel_colors]
        else:
            # Fallback to default colors
            colors = ["#ff0000", "#00cc00", "#0066ff", "#333333"]

        for idx, (label, (xs, ys)) in enumerate(series.items()):
            pen = pg.mkPen(color=colors[idx] if idx < len(colors) else "#7f8c8d", width=2) if pg else None
            self.prof_widget.plot(xs, ys, pen=pen, name=label if label != "I" else "Intensity")

        # Set title and labels
        orientation_label = {"h": "Horizontal", "v": "Vertical", "d": "Diagonal"}[orientation]
        mode_label = "Absolute" if x_mode == "absolute" else "Relative"
        self.prof_widget.setTitle(f"Profile ({orientation_label}, {mode_label})", color="#2c3e50", size="12pt")
        self.prof_widget.setLabel("bottom", "Position" if x_mode == "relative" else "Absolute Position")
        self.prof_widget.setLabel("left", "Intensity")

        # Update statistics table
        self._populate_stats_table(stats_rows)

        # Update button texts
        if orientation == "h":
            self.orientation_btn.setText("Horizontal")
        else:
            self.orientation_btn.setText("Vertical")

        if x_mode == "relative":
            self.xmode_btn.setText("Relative")
        else:
            self.xmode_btn.setText("Absolute")

    def _populate_stats_table(self, rows: list[dict]):
        """Populate stats table from computed statistics."""
        from PySide6.QtWidgets import QTableWidgetItem
        from PySide6.QtGui import QPixmap, QColor
        from PySide6.QtCore import Qt

        dlg = self
        color_map = {}
        assign_colors = None
        visited = set()
        while dlg is not None and id(dlg) not in visited:
            visited.add(id(dlg))
            if hasattr(dlg, "overlay_color_map"):
                color_map = getattr(dlg, "overlay_color_map", {}) or {}
                assign_colors = getattr(dlg, "_assign_overlay_colors", None)
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
                # Attempt underscore fallback similar to histogram
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
            mdi = QTableWidgetItem(f"{int(r['median'])}" if r["is_int"] else f"{r['median']:.4f}")
            mdi.setTextAlignment(Qt.AlignCenter)
            mini = QTableWidgetItem(f"{int(r['min'])}" if r["is_int"] else f"{r['min']:.4f}")
            mini.setTextAlignment(Qt.AlignCenter)
            maxi = QTableWidgetItem(f"{int(r['max'])}" if r["is_int"] else f"{r['max']:.4f}")
            maxi.setTextAlignment(Qt.AlignCenter)
            self.prof_stats_table.setItem(row_idx, 1, mi)
            self.prof_stats_table.setItem(row_idx, 2, si)
            self.prof_stats_table.setItem(row_idx, 3, mdi)
            self.prof_stats_table.setItem(row_idx, 4, mini)
            self.prof_stats_table.setItem(row_idx, 5, maxi)
            for col in range(1, 6):
                item = self.prof_stats_table.item(row_idx, col)
                if item is not None:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
