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

    def __init__(
        self,
        pyqtgraph_available: bool,
        on_save_viewbox_state: Optional[Callable[[object], None]] = None,
        on_connect_plot_controls: Optional[Callable[[object], None]] = None,
        parent=None,
    ):
        super().__init__(parent)

        self.hist_widget = None

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

        # Stats table
        self.stats_table = QTableWidget()
        stats_headers = ["ch", "Mean", "Std", "Median", "Min", "Max"]
        self.stats_table.setColumnCount(len(stats_headers))
        self.stats_table.setHorizontalHeaderLabels(stats_headers)
        self.stats_table.setRowCount(0)
        self.stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.stats_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.stats_table.setSelectionBehavior(QTableWidget.SelectItems)
        self.stats_table.setMaximumHeight(120)
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

    def update(
        self,
        series: dict,
        stats_rows: list[dict],
        plot_settings: dict,
        apply_log: bool = False,
        is_integer_type: bool = False,
        channel_colors: list = None,
    ):
        """Update histogram plot and statistics table with pre-computed data.

        Parameters
        ----------
        series: dict
            Mapping of label -> (xs, ys) for histogram data
        stats_rows: list[dict]
            List of dicts with keys: ch, mean, std, median, min, max, is_int
        plot_settings: dict
            Plot configuration (grid, log, etc.)
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
            yplot = ys
            if apply_log:
                import numpy as np

                with np.errstate(divide="ignore"):
                    yplot = np.log10(ys.astype(float) + 1.0)
            self.hist_widget.plot(xs, yplot, pen=pen, name=label if label != "I" else "Intensity")

        # Set title
        self.hist_widget.setTitle("Intensity Histogram", color="#2c3e50", size="12pt")

        # Configure x-axis for integer types
        if is_integer_type and pg is not None:
            try:
                axis = self.hist_widget.getAxis("bottom")
                # Force integer ticks for integer data types
                axis.setStyle(tickTextOffset=10)
                # Use a custom tick spacing that ensures integer values
                import numpy as np

                if series:
                    first_key = next(iter(series))
                    xs_sample = series[first_key][0]
                    x_min, x_max = xs_sample.min(), xs_sample.max()
                    x_range = x_max - x_min
                    # Choose appropriate tick spacing based on range
                    if x_range <= 16:
                        tick_spacing = 1
                    elif x_range <= 64:
                        tick_spacing = 4
                    elif x_range <= 256:
                        tick_spacing = 16
                    elif x_range <= 1024:
                        tick_spacing = 64
                    else:
                        tick_spacing = 256

                    # Generate integer tick positions
                    tick_start = int(np.ceil(x_min / tick_spacing)) * tick_spacing
                    tick_positions = []
                    current_tick = tick_start
                    while current_tick <= x_max:
                        tick_positions.append(current_tick)
                        current_tick += tick_spacing

                    if tick_positions:
                        ticks = [[(pos, str(int(pos))) for pos in tick_positions]]
                        axis.setTicks(ticks)
            except Exception:
                pass  # If axis configuration fails, just use default

        # Update statistics table
        self._populate_stats_table(stats_rows)

    def _populate_stats_table(self, rows: list[dict]):
        """Populate stats table from computed statistics."""
        from PySide6.QtWidgets import QTableWidgetItem

        self.stats_table.setRowCount(len(rows))
        for row_idx, r in enumerate(rows):
            ch_item = QTableWidgetItem(r["ch"])
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
            self.stats_table.setItem(row_idx, 1, mi)
            self.stats_table.setItem(row_idx, 2, si)
            self.stats_table.setItem(row_idx, 3, mdi)
            self.stats_table.setItem(row_idx, 4, mini)
            self.stats_table.setItem(row_idx, 5, maxi)
            for col in range(1, 6):
                item = self.stats_table.item(row_idx, col)
                if item is not None:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
