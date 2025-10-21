"""Analysis dialog with tabbed interface for image analysis.

This module provides the main AnalysisDialog which displays:
- Info tab: Selection size and position
- Histogram tab: Intensity histogram with customizable channels and statistical information
- Profile tab: Line profile (horizontal/vertical/diagonal) with absolute/relative modes and statistical information
- Metadata tab: Image metadata in table format with EXIF information

The dialog supports pyqtgraph-based interactive plots with right-click
context menus for plot configuration. If pyqtgraph is not available, the
histogram and profile tabs will show empty placeholders.

Statistical information displayed includes:
- Mean: Average intensity value
- Std: Standard deviation of intensity values
- Min: Minimum intensity value
- Max: Maximum intensity value
- Median: Median intensity value

Dependencies:
    - pyqtgraph (optional): For fast histogram and profile plotting
    - numpy: For data processing
    - exifread: For comprehensive EXIF metadata reading
"""

from typing import Optional
import numpy as np

from PySide6.QtCore import QRect, Qt
from ....core.image_io import get_image_metadata
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QTextBrowser,
    QPushButton,
    QDialogButtonBox,
    QWidget,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QSizePolicy,
    QGroupBox,
)
from PySide6.QtGui import QGuiApplication

try:
    import pyqtgraph as pg
    from pyqtgraph import PlotWidget

    PYQTGRAPH_AVAILABLE = True

except ImportError:
    pg = None
    PlotWidget = None
    PYQTGRAPH_AVAILABLE = False

from .controls import ChannelsDialog
from .widgets import CopyableTableWidget


class AnalysisDialog(QDialog):
    """Main analysis dialog with tabbed interface for Info, Histogram, and Profile.

    This dialog provides four tabs for analyzing image selections:

    1. Metadata Tab:
       - Displays comprehensive image metadata including EXIF information
       - Copyable table format

    2. Info Tab:
       - Displays selection dimensions and position

    3. Histogram Tab:
       - Shows intensity distribution across all channels
       - Statistical information: mean, std, min, max, median for visible channels
       - Customizable via "Channels..." button
       - "Copy data" exports histogram as CSV to clipboard

    4. Profile Tab:
       - Shows averaged intensity profile along a direction
       - Statistical information: mean, std, min, max, median for visible channels
       - Customizable via "Channels..." button
       - "Copy data" exports profile as CSV to clipboard

    The dialog is modeless and updates automatically when the parent
    viewer's selection changes (via set_image_and_rect).

    Args:
        parent: Parent widget (typically ImageViewer)
        image_array: NumPy array of the image or selection
        image_rect: QRect defining the selection in image coordinates

    Usage:
        dlg = AnalysisDialog(parent, image_array=arr, image_rect=rect)
        dlg.show()  # Modeless

        # Update when selection changes:
        dlg.set_image_and_rect(new_array, new_rect)

    Note:
        Requires pyqtgraph for histogram and profile plots. If pyqtgraph
        is not available, those tabs will be empty.
    """

    def __init__(
        self,
        parent=None,
        image_array: Optional[np.ndarray] = None,
        image_rect: Optional[QRect] = None,
        image_path: Optional[str] = None,
        pil_image=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Analysis")
        self.resize(900, 600)
        self.image_array = image_array
        self.image_rect = image_rect
        self.image_path = image_path
        self.pil_image = pil_image  # Store PIL image for metadata extraction

        # state
        self.profile_orientation = "h"  # "h", "v", or "d" (diagonal)
        self.x_mode = "relative"
        self.hist_yscale = "linear"
        self.channel_checks: list[bool] = []

        self.last_hist_data = {}
        self.last_profile_data = {}

        self._build_ui()

        if self.image_array is not None:
            self.update_contents()

    def _build_ui(self):
        main = QVBoxLayout(self)
        self.tabs = QTabWidget()
        main.addWidget(self.tabs)

        # Metadata tab
        metadata_tab = QWidget()
        ml = QVBoxLayout(metadata_tab)

        # Create table for metadata display with Ctrl+C support
        self.metadata_table = CopyableTableWidget()
        self.metadata_table.setColumnCount(2)
        self.metadata_table.setHorizontalHeaderLabels(["Key", "Value"])
        self.metadata_table.horizontalHeader().setStretchLastSection(True)
        self.metadata_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.metadata_table.setEditTriggers(QTableWidget.NoEditTriggers)  # 編集不可
        self.metadata_table.setSelectionMode(QTableWidget.ExtendedSelection)  # 複数選択可能
        self.metadata_table.setSelectionBehavior(QTableWidget.SelectItems)  # セル単位で選択
        ml.addWidget(self.metadata_table)

        # Add copy button
        self.metadata_copy_btn = QPushButton("クリップボードにコピー")
        self.metadata_copy_btn.clicked.connect(self.copy_metadata_to_clipboard)
        ml.addWidget(self.metadata_copy_btn)

        self.tabs.addTab(metadata_tab, "Metadata")

        # Info tab
        info_tab = QWidget()
        il = QVBoxLayout(info_tab)
        self.info_browser = QTextBrowser()
        self.info_browser.setReadOnly(True)
        il.addWidget(self.info_browser)
        self.tabs.addTab(info_tab, "Info")

        # Profile tab
        prof_tab = QWidget()
        pl = QHBoxLayout(prof_tab)

        # Left side: plot and statistics in vertical layout
        prof_left_layout = QVBoxLayout()

        if PYQTGRAPH_AVAILABLE:
            self.prof_widget = PlotWidget()
            self.prof_widget.setLabel("left", "Intensity")
            self.prof_widget.setLabel("bottom", "Position")

            # Style configuration for better UI integration (no border)
            self.prof_widget.setBackground("white")
            self.prof_widget.showGrid(x=True, y=True, alpha=0.4)  # More visible grid lines
            self.prof_widget.getAxis("left").setPen(pg.mkPen(color="#7f8c8d", width=1))  # Darker axis lines
            self.prof_widget.getAxis("bottom").setPen(pg.mkPen(color="#7f8c8d", width=1))  # Darker axis lines
            self.prof_widget.getAxis("left").setTextPen(pg.mkPen(color="#2c3e50"))
            self.prof_widget.getAxis("bottom").setTextPen(pg.mkPen(color="#2c3e50"))

            # Enable right-click menu and disable drag operations
            self.prof_widget.setMenuEnabled(True)
            # Configure ViewBox for analysis use
            view_box = self.prof_widget.getViewBox()
            view_box.setMouseEnabled(x=False, y=False)  # Disable drag/zoom
            # Ensure axes are in Auto state
            view_box.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)

            prof_left_layout.addWidget(self.prof_widget, 3)
        else:
            self.prof_widget = None

        # Statistics display (table, read-only, selectable cells)
        # Table layout: rows = channels, columns = [ch, Mean, Std, Median, Min, Max]
        self.prof_stats_table = QTableWidget()
        stats_headers = ["ch", "Mean", "Std", "Median", "Min", "Max"]
        self.prof_stats_table.setColumnCount(len(stats_headers))
        self.prof_stats_table.setHorizontalHeaderLabels(stats_headers)
        self.prof_stats_table.setRowCount(0)  # filled per visible channel
        self.prof_stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.prof_stats_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.prof_stats_table.setSelectionBehavior(QTableWidget.SelectItems)
        self.prof_stats_table.setMaximumHeight(120)
        # Use a fixed total width for the stats table and fixed column widths.
        # Make the 'ch' column wider for readability, and distribute remaining
        # width evenly among the numeric columns.
        total_w = 600
        ch_w = 120
        other_w = max(60, (total_w - ch_w) // (self.prof_stats_table.columnCount() - 1))
        header = self.prof_stats_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Fixed)
        # Set the widths: column 0 is ch, others are equal
        self.prof_stats_table.setColumnWidth(0, ch_w)
        for c in range(1, self.prof_stats_table.columnCount()):
            self.prof_stats_table.setColumnWidth(c, other_w)
        # Apply fixed table width and sensible font size
        self.prof_stats_table.setFixedWidth(ch_w + other_w * (self.prof_stats_table.columnCount() - 1) + 2)
        self.prof_stats_table.setStyleSheet("QTableWidget { font-size: 10pt; }")
        # Disable horizontal scrollbar and hide vertical index
        self.prof_stats_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.prof_stats_table.verticalHeader().setVisible(False)
        prof_left_layout.addWidget(self.prof_stats_table, 0)

        pl.addLayout(prof_left_layout, 1)
        pv = QVBoxLayout()
        # Add left and right margins to the button area
        pv.setContentsMargins(10, 10, 10, 10)
        pv.setSpacing(8)  # Add spacing between groups

        # Channel control group
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
        channels_layout.setContentsMargins(8, 5, 8, 8)  # Add padding inside group
        self.prof_channels_btn = QPushButton("Configure...")
        self.prof_channels_btn.setMinimumWidth(100)  # Set minimum width for better appearance
        self.prof_channels_btn.clicked.connect(self._on_prof_channels)
        channels_layout.addWidget(self.prof_channels_btn)
        pv.addWidget(channels_group)

        # Profile display settings group
        display_group = QGroupBox("Display Settings")
        display_group.setStyleSheet(
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
        display_layout = QVBoxLayout(display_group)
        display_layout.setContentsMargins(8, 5, 8, 8)  # Add padding inside group

        self.prof_orientation_btn = QPushButton("Horizontal")
        self.prof_orientation_btn.setMinimumWidth(100)  # Set minimum width for better appearance
        self.prof_orientation_btn.clicked.connect(self._on_prof_orientation_toggle)
        display_layout.addWidget(self.prof_orientation_btn)

        self.prof_xmode_btn = QPushButton("Relative")
        self.prof_xmode_btn.setMinimumWidth(100)  # Set minimum width for better appearance
        self.prof_xmode_btn.clicked.connect(self._on_prof_xmode_toggle)
        display_layout.addWidget(self.prof_xmode_btn)
        pv.addWidget(display_group)

        # Data export group
        export_group = QGroupBox("Export")
        export_group.setStyleSheet(
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
        export_layout = QVBoxLayout(export_group)
        export_layout.setContentsMargins(8, 5, 8, 8)  # Add padding inside group
        self.prof_copy_btn = QPushButton("Copy data")
        self.prof_copy_btn.setMinimumWidth(100)  # Set minimum width for better appearance
        self.prof_copy_btn.clicked.connect(self.copy_profile_to_clipboard)
        export_layout.addWidget(self.prof_copy_btn)
        # Copy statistics button for profile
        self.prof_copy_stats_btn = QPushButton("Copy stats")
        self.prof_copy_stats_btn.setMinimumWidth(100)
        self.prof_copy_stats_btn.clicked.connect(self.copy_prof_stats_to_clipboard)
        export_layout.addWidget(self.prof_copy_stats_btn)
        pv.addWidget(export_group)

        pv.addStretch(1)
        pl.addLayout(pv)
        self.tabs.addTab(prof_tab, "Profile")

        # Histogram tab
        hist_tab = QWidget()
        hl = QHBoxLayout(hist_tab)

        # Left side: plot and statistics in vertical layout
        hist_left_layout = QVBoxLayout()

        if PYQTGRAPH_AVAILABLE:
            self.hist_widget = PlotWidget()
            self.hist_widget.setLabel("left", "Count")
            self.hist_widget.setLabel("bottom", "Intensity")

            # Style configuration for better UI integration (no border)
            self.hist_widget.setBackground("white")
            self.hist_widget.showGrid(x=True, y=True, alpha=0.4)  # More visible grid lines
            self.hist_widget.getAxis("left").setPen(pg.mkPen(color="#7f8c8d", width=1))  # Darker axis lines
            self.hist_widget.getAxis("bottom").setPen(pg.mkPen(color="#7f8c8d", width=1))  # Darker axis lines
            self.hist_widget.getAxis("left").setTextPen(pg.mkPen(color="#2c3e50"))
            self.hist_widget.getAxis("bottom").setTextPen(pg.mkPen(color="#2c3e50"))

            # Enable right-click menu and disable drag operations
            self.hist_widget.setMenuEnabled(True)
            # Configure ViewBox for analysis use
            view_box = self.hist_widget.getViewBox()
            view_box.setMouseEnabled(x=False, y=False)  # Disable drag/zoom
            # Ensure axes are in Auto state
            view_box.enableAutoRange(axis=pg.ViewBox.XYAxes, enable=True)

            hist_left_layout.addWidget(self.hist_widget, 3)
        else:
            self.hist_widget = None

        # Statistics display (table, read-only, selectable cells)
        # Table layout: rows = channels, columns = [ch, Mean, Std, Median, Min, Max]
        self.hist_stats_table = QTableWidget()
        stats_headers = ["ch", "Mean", "Std", "Median", "Min", "Max"]
        self.hist_stats_table.setColumnCount(len(stats_headers))
        self.hist_stats_table.setHorizontalHeaderLabels(stats_headers)
        self.hist_stats_table.setRowCount(0)
        self.hist_stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.hist_stats_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.hist_stats_table.setSelectionBehavior(QTableWidget.SelectItems)
        self.hist_stats_table.setMaximumHeight(120)
        # Make header stretch to available width to avoid horizontal scrollbars.
        h_header = self.hist_stats_table.horizontalHeader()
        total_w = 600
        ch_w = 120
        other_w = max(60, (total_w - ch_w) // (self.hist_stats_table.columnCount() - 1))
        h_header.setSectionResizeMode(QHeaderView.Fixed)
        self.hist_stats_table.setColumnWidth(0, ch_w)
        for c in range(1, self.hist_stats_table.columnCount()):
            self.hist_stats_table.setColumnWidth(c, other_w)
        self.hist_stats_table.setFixedWidth(ch_w + other_w * (self.hist_stats_table.columnCount() - 1) + 2)
        self.hist_stats_table.setStyleSheet("QTableWidget { font-size: 10pt; }")
        self.hist_stats_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        # Hide row index (vertical header)
        self.hist_stats_table.verticalHeader().setVisible(False)
        hist_left_layout.addWidget(self.hist_stats_table, 0)

        hl.addLayout(hist_left_layout, 1)

        vcol = QVBoxLayout()
        # Add left and right margins to the button area
        vcol.setContentsMargins(10, 10, 10, 10)
        vcol.setSpacing(8)  # Add spacing between groups

        # Channel control group
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
        channels_layout.setContentsMargins(8, 5, 8, 8)  # Add padding inside group
        self.hist_channels_btn = QPushButton("Configure...")
        self.hist_channels_btn.setMinimumWidth(100)  # Set minimum width for better appearance
        self.hist_channels_btn.clicked.connect(self._on_hist_channels)
        channels_layout.addWidget(self.hist_channels_btn)
        vcol.addWidget(channels_group)

        # Data export group
        export_group = QGroupBox("Export")
        export_group.setStyleSheet(
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
        export_layout = QVBoxLayout(export_group)
        export_layout.setContentsMargins(8, 5, 8, 8)  # Add padding inside group
        self.hist_copy_btn = QPushButton("Copy data")
        self.hist_copy_btn.setMinimumWidth(100)  # Set minimum width for better appearance
        self.hist_copy_btn.clicked.connect(self.copy_histogram_to_clipboard)
        export_layout.addWidget(self.hist_copy_btn)
        # Copy statistics button for histogram
        self.hist_copy_stats_btn = QPushButton("Copy stats")
        self.hist_copy_stats_btn.setMinimumWidth(100)
        self.hist_copy_stats_btn.clicked.connect(self.copy_hist_stats_to_clipboard)
        export_layout.addWidget(self.hist_copy_stats_btn)
        vcol.addWidget(export_group)

        vcol.addStretch(1)
        hl.addLayout(vcol)
        self.tabs.addTab(hist_tab, "Histogram")

        box = QDialogButtonBox(QDialogButtonBox.Close)
        box.rejected.connect(self.reject)
        box.accepted.connect(self.accept)
        main.addWidget(box)

    def set_image_and_rect(
        self,
        image_array: Optional[np.ndarray],
        image_rect: Optional[QRect],
        image_path: Optional[str] = None,
        pil_image=None,
    ):
        """ダイアログの表示内容を新しい画像データや選択矩形で更新します。

        このメソッドは外部（親ビューア）から頻繁に呼ばれる想定で、
        モデルを更新したあと内部表示を再構築する `update_contents` を呼び出します。

        引数:
            image_array: 画像または選択領域の NumPy 配列
            image_rect: 画像座標系での選択矩形（QRect）
            image_path: 画像ファイルのパス（メタデータ取得に利用）
            pil_image: PIL.Image オブジェクトが既にある場合はそれを渡すとメタデータ取得が高速になります
        """
        self.image_array = image_array
        self.image_rect = image_rect
        if image_path is not None:
            self.image_path = image_path
        if pil_image is not None:
            self.pil_image = pil_image
        self.update_contents()

    def set_current_tab(self, tab):
        """タブを名前（'Histogram','Profile','Info' の先頭部分一致）またはインデックスで切り替えます。

        引数:
            tab: タブ名の文字列あるいはインデックス（int）
        """
        if tab is None:
            return
        if isinstance(tab, int):
            if 0 <= tab < self.tabs.count():
                self.tabs.setCurrentIndex(tab)
            return
        t = str(tab).lower()
        for i in range(self.tabs.count()):
            if self.tabs.tabText(i).lower().startswith(t):
                self.tabs.setCurrentIndex(i)
                return

    def _on_hist_channels(self):
        """ヒストグラム用のチャネル選択ダイアログを作成して表示します。

        すでに画像データがない場合は何もしません。
        """
        if self.image_array is None:
            return
        nch = self.image_array.shape[2] if self.image_array.ndim == 3 else 1

        def immediate_update(new_checks):
            """Callback for immediate graph update when checkboxes change."""
            self.channel_checks = new_checks
            self.update_contents()

        # Create and show modeless dialog with immediate updates
        dlg = ChannelsDialog(self, nch, self.channel_checks, callback=immediate_update)

        # Position dialog near the histogram channels button
        button_pos = self.hist_channels_btn.mapToGlobal(self.hist_channels_btn.rect().topRight())
        dlg.move(button_pos.x() + 10, button_pos.y())

        dlg.show()  # Show modeless dialog without blocking

    def _on_prof_channels(self):
        """プロファイル用のチャネル選択ダイアログを作成して表示します。

        すでに画像データがない場合は何もしません。
        """
        if self.image_array is None:
            return
        nch = self.image_array.shape[2] if self.image_array.ndim == 3 else 1

        def immediate_update(new_checks):
            """Callback for immediate graph update when checkboxes change."""
            self.channel_checks = new_checks
            self.update_contents()

        # Create and show modeless dialog with immediate updates
        dlg = ChannelsDialog(self, nch, self.channel_checks, callback=immediate_update)

        # Position dialog near the profile channels button
        button_pos = self.prof_channels_btn.mapToGlobal(self.prof_channels_btn.rect().topRight())
        dlg.move(button_pos.x() + 10, button_pos.y())

        dlg.show()  # Show modeless dialog without blocking

    def update_contents(self):
        """現在の画像データ／設定をもとに全タブの内容を再描画します。

        - 選択領域が存在する場合はその領域のみを扱います
        - メタデータタブは常に更新されます
        - pyqtgraph が利用可能な場合はヒストグラム／プロファイルをプロットします
        """
        arr = self.image_array
        if arr is None:
            self.info_browser.setPlainText("No data")
            self._update_metadata()
            return
        if self.image_rect is not None:
            x, y, w, h = (
                int(self.image_rect.x()),
                int(self.image_rect.y()),
                int(self.image_rect.width()),
                int(self.image_rect.height()),
            )
            arr = arr[y : y + h, x : x + w]

        h, w = arr.shape[:2]
        info_lines = [f"Selection size: {w} x {h}"]
        if self.image_rect is not None:
            info_lines.append(f"Start: ({int(self.image_rect.x())}, {int(self.image_rect.y())})")
        self.info_browser.setPlainText("\n".join(info_lines))

        # Update metadata tab (always update when image changes)
        self._update_metadata()

        if not PYQTGRAPH_AVAILABLE:
            return

        # Histogram
        self.hist_widget.clear()
        self.last_hist_data = {}
        # Improved color palette for better visibility of 3 channels
        colors = ["#ff0000", "#00cc00", "#0066ff", "#333333"]  # Bright Red, Green, Blue, Dark gray

        if arr.ndim == 3 and arr.shape[2] > 1:
            nch = arr.shape[2]
            if not self.channel_checks:
                self.channel_checks = [True] * nch
            # Adjust channel_checks length to match current number of channels
            elif len(self.channel_checks) < nch:
                # Extend with True for new channels
                self.channel_checks.extend([True] * (nch - len(self.channel_checks)))
            for c in range(nch):
                data = arr[:, :, c].ravel()
                hist, bins = np.histogram(data, bins=256, range=(0, 255))
                xs = (bins[:-1] + bins[1:]) / 2.0
                self.last_hist_data[f"C{c}"] = (xs, hist)
                if self.channel_checks[c]:
                    # Line only, no symbols
                    pen = pg.mkPen(color=colors[c] if c < len(colors) else "#7f8c8d", width=2)
                    self.hist_widget.plot(xs, hist, pen=pen, name=f"C{c}")
        else:
            gray = arr if arr.ndim == 2 else arr[:, :, 0]
            hist, bins = np.histogram(gray.ravel(), bins=256, range=(0, 255))
            xs = (bins[:-1] + bins[1:]) / 2.0
            self.last_hist_data["I"] = (xs, hist)
            # Line only, no symbols
            pen = pg.mkPen(color="#333333", width=2)
            self.hist_widget.plot(xs, hist, pen=pen, name="Intensity")

        # Set title with improved styling
        self.hist_widget.setTitle("Intensity Histogram", color="#2c3e50", size="12pt")

        # Apply log scale if needed
        if hasattr(self, "hist_yscale") and self.hist_yscale == "log":
            self.hist_widget.setLogMode(y=True)
        else:
            self.hist_widget.setLogMode(y=False)

        # Update histogram statistics
        self._update_histogram_statistics(arr)

        # Profile
        self.prof_widget.clear()
        self.last_profile_data = {}
        # Use same improved color palette as histogram
        colors = ["#ff0000", "#00cc00", "#0066ff", "#333333"]  # Bright Red, Green, Blue, Dark gray

        if arr.ndim == 3 and arr.shape[2] > 1:
            nch = arr.shape[2]
            if not self.channel_checks:
                self.channel_checks = [True] * nch
            # Adjust channel_checks length to match current number of channels
            elif len(self.channel_checks) < nch:
                # Extend with True for new channels
                self.channel_checks.extend([True] * (nch - len(self.channel_checks)))
            for c in range(nch):
                prof = self._compute_profile(arr[:, :, c])
                if self.x_mode == "absolute" and self.image_rect is not None:
                    offset = self._get_profile_offset()
                    xs2 = np.arange(prof.size) + offset
                else:
                    xs2 = np.arange(prof.size)
                self.last_profile_data[f"C{c}"] = (xs2, prof)
                if self.channel_checks[c]:
                    # Line only, no symbols
                    pen = pg.mkPen(color=colors[c] if c < len(colors) else "#7f8c8d", width=2)
                    self.prof_widget.plot(xs2, prof, pen=pen, name=f"C{c}")
        else:
            gray_data = arr if arr.ndim == 2 else arr[:, :, 0]
            prof = self._compute_profile(gray_data)
            if self.x_mode == "absolute" and self.image_rect is not None:
                offset = self._get_profile_offset()
                xs2 = np.arange(prof.size) + offset
            else:
                xs2 = np.arange(prof.size)
            self.last_profile_data["I"] = (xs2, prof)
            # Line only, no symbols
            pen = pg.mkPen(color="#333333", width=2)
            self.prof_widget.plot(xs2, prof, pen=pen, name="Intensity")

        orientation_label = {"h": "Horizontal", "v": "Vertical", "d": "Diagonal"}[self.profile_orientation]
        mode_label = "Absolute" if self.x_mode == "absolute" else "Relative"
        # Set title with improved styling
        self.prof_widget.setTitle(f"Profile ({orientation_label}, {mode_label})", color="#2c3e50", size="12pt")
        self.prof_widget.setLabel("bottom", "Position" if self.x_mode == "relative" else "Absolute Position")
        self.prof_widget.setLabel("left", "Intensity")

        # Update profile statistics
        self._update_profile_statistics(arr)

        # Ensure both widgets are in true "Auto" state for axes
        if PYQTGRAPH_AVAILABLE:
            # Set histogram to auto range state (order is important)
            hist_vb = self.hist_widget.getViewBox()
            hist_vb.autoRange()  # First fit to current data
            hist_vb.enableAutoRange(axis=pg.ViewBox.XYAxes)  # Then enable auto for future

            # Set profile to auto range state (order is important)
            prof_vb = self.prof_widget.getViewBox()
            prof_vb.autoRange()  # First fit to current data
            prof_vb.enableAutoRange(axis=pg.ViewBox.XYAxes)  # Then enable auto for future

        # Update button texts to reflect current state
        if hasattr(self, "prof_orientation_btn"):
            if self.profile_orientation == "h":
                self.prof_orientation_btn.setText("Horizontal")
            else:
                self.prof_orientation_btn.setText("Vertical")

        if hasattr(self, "prof_xmode_btn"):
            if self.x_mode == "relative":
                self.prof_xmode_btn.setText("Relative")
            else:
                self.prof_xmode_btn.setText("Absolute")

    def _update_metadata(self):
        """Update the metadata tab with image file information in table format."""
        if not hasattr(self, "metadata_table"):
            return

        if self.image_path is None or not self.image_path:
            self.metadata_table.setRowCount(1)
            self.metadata_table.setItem(0, 0, QTableWidgetItem("Error"))
            self.metadata_table.setItem(0, 1, QTableWidgetItem("No file path available"))
            return

        try:
            # Use cached PIL image if available, otherwise fall back to file path
            if self.pil_image is not None:
                metadata = get_image_metadata(self.pil_image, pil_image=self.pil_image)
            else:
                metadata = get_image_metadata(self.image_path)

            if not metadata:
                self.metadata_table.setRowCount(1)
                self.metadata_table.setItem(0, 0, QTableWidgetItem("Info"))
                self.metadata_table.setItem(0, 1, QTableWidgetItem("No metadata available"))
                return

            # Prepare data in order: Basic info first, then EXIF tags
            rows = []

            # 1. Basic information (from PIL)
            basic_keys = ["Filepath", "Format", "Size", "DataType", "Mode"]
            for key in basic_keys:
                if key in metadata:
                    value_str = str(metadata[key])
                    rows.append((key, value_str))

            # 2. EXIF tags (sorted alphabetically)
            exif_items = [(k, v) for k, v in metadata.items() if k not in basic_keys]
            for key, value in sorted(exif_items):
                value_str = str(value)
                rows.append((key, value_str))

            # Populate table
            self.metadata_table.setRowCount(len(rows))
            for i, (key, value) in enumerate(rows):
                self.metadata_table.setItem(i, 0, QTableWidgetItem(key))
                self.metadata_table.setItem(i, 1, QTableWidgetItem(value))

            # Store metadata for copying
            self.last_metadata = rows

        except Exception as e:
            self.metadata_table.setRowCount(1)
            self.metadata_table.setItem(0, 0, QTableWidgetItem("Error"))
            self.metadata_table.setItem(0, 1, QTableWidgetItem(f"Error reading metadata: {str(e)}"))
            self.last_metadata = []

    def copy_metadata_to_clipboard(self):
        """Copy metadata as comma-separated text to clipboard."""
        if not hasattr(self, "last_metadata") or not self.last_metadata:
            QMessageBox.information(self, "Copy", "No metadata to copy.")
            return

        # Create comma-separated format
        lines = ["Key,Value"]  # Header
        for key, value in self.last_metadata:
            lines.append(f"{key},{value}")

        text = "\n".join(lines)
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copy", f"Copied {len(self.last_metadata)} metadata entries to clipboard.")

    def copy_histogram_to_clipboard(self):
        """Copy histogram data as CSV to clipboard."""
        if not getattr(self, "last_hist_data", None):
            QMessageBox.information(self, "Copy", "No data.")
            return

        # Use numpy array operations for efficient data processing
        keys = list(self.last_hist_data.keys())
        xs = self.last_hist_data[keys[0]][0]

        # Build data matrix efficiently
        data_matrix = np.column_stack([xs] + [self.last_hist_data[k][1] for k in keys])

        # Create header and format data
        header = ",".join(["x"] + keys)
        data_lines = [",".join(map(str, row.astype(int))) for row in data_matrix]

        text = "\n".join([header] + data_lines)
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copy", "Histogram copied to clipboard.")

    def copy_profile_to_clipboard(self):
        """Copy profile data as CSV to clipboard."""
        if not getattr(self, "last_profile_data", None):
            QMessageBox.information(self, "Copy", "No data.")
            return

        # Use numpy array operations for efficient data processing
        keys = list(self.last_profile_data.keys())
        xs = self.last_profile_data[keys[0]][0]

        # Build data matrix efficiently
        data_matrix = np.column_stack([xs] + [self.last_profile_data[k][1] for k in keys])

        # Create header and format data
        header = ",".join(["x"] + keys)
        data_lines = [",".join(map(str, row)) for row in data_matrix]

        text = "\n".join([header] + data_lines)
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copy", "Profile copied to clipboard.")

    def _table_selection_to_csv(self, table: QTableWidget) -> str:
        """Convert the selected region of a QTableWidget to CSV text.

        If multiple non-contiguous ranges are selected, the first range is used.
        """
        ranges = table.selectedRanges()
        cols = table.columnCount()
        header_labels = [
            table.horizontalHeaderItem(c).text() if table.horizontalHeaderItem(c) is not None else ""
            for c in range(cols)
        ]

        if not ranges:
            # If nothing selected, export whole table including header
            rows = table.rowCount()
            out_lines = []
            out_lines.append(",".join(header_labels))
            for r in range(rows):
                row_vals = []
                for c in range(cols):
                    item = table.item(r, c)
                    row_vals.append(item.text() if item is not None else "")
                out_lines.append(",".join(row_vals))
            return "\n".join(out_lines)

        r = ranges[0]
        # Build header for selected columns
        sel_header = [header_labels[c] for c in range(r.leftColumn(), r.rightColumn() + 1)]
        out_lines = [",".join(sel_header)]
        for row in range(r.topRow(), r.bottomRow() + 1):
            vals = []
            for col in range(r.leftColumn(), r.rightColumn() + 1):
                item = table.item(row, col)
                vals.append(item.text() if item is not None else "")
            out_lines.append(",".join(vals))
        return "\n".join(out_lines)

    def _table_to_csv(self, table: QTableWidget) -> str:
        """Export entire table (with header) to CSV text."""
        cols = table.columnCount()
        header_labels = [
            table.horizontalHeaderItem(c).text() if table.horizontalHeaderItem(c) is not None else ""
            for c in range(cols)
        ]
        rows = table.rowCount()
        out_lines = [",".join(header_labels)]
        for r in range(rows):
            row_vals = [table.item(r, c).text() if table.item(r, c) is not None else "" for c in range(cols)]
            out_lines.append(",".join(row_vals))
        return "\n".join(out_lines)

    def copy_hist_stats_to_clipboard(self):
        if not hasattr(self, "hist_stats_table"):
            QMessageBox.information(self, "Copy", "No histogram stats to copy.")
            return
        text = self._table_to_csv(self.hist_stats_table)
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copy", "Histogram stats copied to clipboard.")

    def copy_prof_stats_to_clipboard(self):
        if not hasattr(self, "prof_stats_table"):
            QMessageBox.information(self, "Copy", "No profile stats to copy.")
            return
        text = self._table_to_csv(self.prof_stats_table)
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copy", "Profile stats copied to clipboard.")

    def _compute_profile(self, channel_data: np.ndarray) -> np.ndarray:
        """Compute intensity profile for a single channel using optimized numpy operations.

        Args:
            channel_data: 2D array (height x width) of pixel values

        Returns:
            1D array of averaged intensity values

        Orientation modes:
            "h": Horizontal - average along vertical axis (returns width-sized array)
            "v": Vertical - average along horizontal axis (returns height-sized array)
            "d": Diagonal - extract pixels along main diagonal (top-left to bottom-right)
        """
        if self.profile_orientation == "h":
            return np.mean(channel_data, axis=0)
        elif self.profile_orientation == "v":
            return np.mean(channel_data, axis=1)
        else:  # diagonal
            h, w = channel_data.shape

            # Handle edge cases first
            if h == 0 or w == 0:
                return np.array([])
            if h == 1 and w == 1:
                return np.array([channel_data[0, 0]])

            # Use numpy diagonal extraction for square images
            if h == w:
                return np.diag(channel_data)

            # For rectangular images, use efficient coordinate generation
            diag_len = min(h, w)
            if diag_len == 1:
                return np.array([channel_data[0, 0]])

            # Generate coordinates using numpy operations
            y_coords = np.linspace(0, h - 1, diag_len, dtype=int)
            x_coords = np.linspace(0, w - 1, diag_len, dtype=int)

            # Extract diagonal values in one operation
            return channel_data[y_coords, x_coords]

    def _get_profile_offset(self) -> int:
        """Get the offset for absolute x-axis mode.

        Returns:
            Offset value based on current orientation and image_rect
        """
        if self.image_rect is None:
            return 0

        # Use dictionary for efficient orientation mapping
        offset_map = {
            "h": self.image_rect.x(),
            "v": self.image_rect.y(),
            "d": min(self.image_rect.x(), self.image_rect.y()),  # diagonal uses top-left corner
        }
        return offset_map.get(self.profile_orientation, 0)

    def _on_prof_orientation_toggle(self):
        """Toggle profile orientation between horizontal and vertical."""
        if self.profile_orientation == "h":
            self.profile_orientation = "v"
            self.prof_orientation_btn.setText("Vertical")
        else:
            self.profile_orientation = "h"
            self.prof_orientation_btn.setText("Horizontal")
        self.update_contents()

    def _on_prof_xmode_toggle(self):
        """Toggle x-axis mode between relative and absolute."""
        if self.x_mode == "relative":
            self.x_mode = "absolute"
            self.prof_xmode_btn.setText("Absolute")
        else:
            self.x_mode = "relative"
            self.prof_xmode_btn.setText("Relative")
        self.update_contents()

    def _update_histogram_statistics(self, arr: np.ndarray):
        """Calculate and display histogram statistics for each channel.

        Args:
            arr: Image array (may be 2D grayscale or 3D color)
        """
        if not hasattr(self, "hist_stats_table"):
            return

        # We'll populate table with rows per channel and fixed columns: ch, Mean, Std, Median, Min, Max
        headers = ["ch", "Mean", "Std", "Median", "Min", "Max"]
        self.hist_stats_table.setColumnCount(len(headers))
        self.hist_stats_table.setHorizontalHeaderLabels(headers)

        if arr.ndim == 3 and arr.shape[2] > 1:
            nch = arr.shape[2]
            if not self.channel_checks:
                self.channel_checks = [True] * nch
            # Adjust channel_checks length to match current number of channels
            elif len(self.channel_checks) < nch:
                # Extend with True for new channels
                self.channel_checks.extend([True] * (nch - len(self.channel_checks)))
            # Rows: one per channel (even if hidden we can choose to skip hidden channels)
            visible_channels = [c for c in range(nch) if self.channel_checks[c]]
            self.hist_stats_table.setRowCount(len(visible_channels))
            for row_idx, c in enumerate(visible_channels):
                data = arr[:, :, c].ravel()
                mean_v = np.mean(data)
                median_v = np.median(data)
                std_v = np.std(data)
                min_v = np.min(data)
                max_v = np.max(data)

                # Show Min/Max/Median as integers when original channel data is integer dtype
                is_int_dtype = np.issubdtype(data.dtype, np.integer)

                ch_item = QTableWidgetItem(str(c))
                ch_item.setFlags(ch_item.flags() & ~Qt.ItemIsEditable)
                ch_item.setTextAlignment(Qt.AlignCenter)
                self.hist_stats_table.setItem(row_idx, 0, ch_item)

                # Format: Mean/Std -> 4 decimal places; Median/Min/Max -> int if original dtype integer else 4 decimals
                mi = QTableWidgetItem(f"{mean_v:.4f}")
                mi.setTextAlignment(Qt.AlignCenter)
                si = QTableWidgetItem(f"{std_v:.4f}")
                si.setTextAlignment(Qt.AlignCenter)
                mdi = QTableWidgetItem(f"{int(median_v)}" if is_int_dtype else f"{median_v:.4f}")
                mdi.setTextAlignment(Qt.AlignCenter)
                mini = QTableWidgetItem(f"{int(min_v)}" if is_int_dtype else f"{min_v:.4f}")
                mini.setTextAlignment(Qt.AlignCenter)
                maxi = QTableWidgetItem(f"{int(max_v)}" if is_int_dtype else f"{max_v:.4f}")
                maxi.setTextAlignment(Qt.AlignCenter)
                self.hist_stats_table.setItem(row_idx, 1, mi)
                self.hist_stats_table.setItem(row_idx, 2, si)
                self.hist_stats_table.setItem(row_idx, 3, mdi)
                self.hist_stats_table.setItem(row_idx, 4, mini)
                self.hist_stats_table.setItem(row_idx, 5, maxi)
                # Make items read-only
                for col in range(1, 6):
                    item = self.hist_stats_table.item(row_idx, col)
                    if item is not None:
                        item.setFlags(item.flags() & ~Qt.ItemIsEditable)

        else:
            # Single channel / grayscale
            gray = arr if arr.ndim == 2 else arr[:, :, 0]
            data = gray.ravel()
            self.hist_stats_table.setRowCount(1)
            ch_item = QTableWidgetItem("0")
            ch_item.setFlags(ch_item.flags() & ~Qt.ItemIsEditable)
            ch_item.setTextAlignment(Qt.AlignCenter)
            self.hist_stats_table.setItem(0, 0, ch_item)
            mean_v = np.mean(data)
            std_v = np.std(data)
            median_v = np.median(data)
            min_v = np.min(data)
            max_v = np.max(data)
            is_int_dtype = np.issubdtype(gray.dtype, np.integer)
            mi = QTableWidgetItem(f"{mean_v:.4f}")
            mi.setTextAlignment(Qt.AlignCenter)
            si = QTableWidgetItem(f"{std_v:.4f}")
            si.setTextAlignment(Qt.AlignCenter)
            mdi = QTableWidgetItem(f"{int(median_v)}" if is_int_dtype else f"{median_v:.4f}")
            mdi.setTextAlignment(Qt.AlignCenter)
            mini = QTableWidgetItem(f"{int(min_v)}" if is_int_dtype else f"{min_v:.4f}")
            mini.setTextAlignment(Qt.AlignCenter)
            maxi = QTableWidgetItem(f"{int(max_v)}" if is_int_dtype else f"{max_v:.4f}")
            maxi.setTextAlignment(Qt.AlignCenter)
            self.hist_stats_table.setItem(0, 1, mi)
            self.hist_stats_table.setItem(0, 2, si)
            self.hist_stats_table.setItem(0, 3, mdi)
            self.hist_stats_table.setItem(0, 4, mini)
            self.hist_stats_table.setItem(0, 5, maxi)
            for col in range(1, 6):
                item = self.hist_stats_table.item(0, col)
                if item is not None:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)

    def _update_profile_statistics(self, arr: np.ndarray):
        """Calculate and display profile statistics for each channel.

        Args:
            arr: Image array (may be 2D grayscale or 3D color)
        """
        if not hasattr(self, "prof_stats_table"):
            return

        # Populate profile stats table with rows per channel and fixed columns ch, Mean, Std, Median, Min, Max
        headers = ["ch", "Mean", "Std", "Median", "Min", "Max"]
        self.prof_stats_table.setColumnCount(len(headers))
        self.prof_stats_table.setHorizontalHeaderLabels(headers)

        if arr.ndim == 3 and arr.shape[2] > 1:
            nch = arr.shape[2]
            if not self.channel_checks:
                self.channel_checks = [True] * nch
            # Adjust channel_checks length to match current number of channels
            elif len(self.channel_checks) < nch:
                # Extend with True for new channels
                self.channel_checks.extend([True] * (nch - len(self.channel_checks)))
            visible_channels = [c for c in range(nch) if self.channel_checks[c]]
            self.prof_stats_table.setRowCount(len(visible_channels))
            for row_idx, c in enumerate(visible_channels):
                prof = self._compute_profile(arr[:, :, c])
                mean_v = np.mean(prof) if prof.size else 0.0
                median_v = np.median(prof) if prof.size else 0.0
                std_v = np.std(prof) if prof.size else 0.0
                min_v = np.min(prof) if prof.size else 0.0
                max_v = np.max(prof) if prof.size else 0.0
                is_int_dtype = np.issubdtype(arr[:, :, c].dtype, np.integer)

                ch_item = QTableWidgetItem(str(c))
                ch_item.setFlags(ch_item.flags() & ~Qt.ItemIsEditable)
                ch_item.setTextAlignment(Qt.AlignCenter)
                self.prof_stats_table.setItem(row_idx, 0, ch_item)

                mi = QTableWidgetItem(f"{mean_v:.4f}")
                mi.setTextAlignment(Qt.AlignCenter)
                si = QTableWidgetItem(f"{std_v:.4f}")
                si.setTextAlignment(Qt.AlignCenter)
                mdi = QTableWidgetItem(f"{int(median_v)}" if is_int_dtype else f"{median_v:.4f}")
                mdi.setTextAlignment(Qt.AlignCenter)
                mini = QTableWidgetItem(f"{int(min_v)}" if is_int_dtype else f"{min_v:.4f}")
                mini.setTextAlignment(Qt.AlignCenter)
                maxi = QTableWidgetItem(f"{int(max_v)}" if is_int_dtype else f"{max_v:.4f}")
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

        else:
            gray_data = arr if arr.ndim == 2 else arr[:, :, 0]
            prof = self._compute_profile(gray_data)
            self.prof_stats_table.setRowCount(1)
            ch_item = QTableWidgetItem("0")
            ch_item.setFlags(ch_item.flags() & ~Qt.ItemIsEditable)
            ch_item.setTextAlignment(Qt.AlignCenter)
            self.prof_stats_table.setItem(0, 0, ch_item)
            mean_v = np.mean(prof) if prof.size else 0.0
            std_v = np.std(prof) if prof.size else 0.0
            mean_v = np.mean(prof) if prof.size else 0.0
            std_v = np.std(prof) if prof.size else 0.0
            median_v = np.median(prof) if prof.size else 0.0
            min_v = np.min(prof) if prof.size else 0.0
            max_v = np.max(prof) if prof.size else 0.0
            is_int_dtype = np.issubdtype(gray_data.dtype, np.integer) if prof.size else False
            self.prof_stats_table.setRowCount(1)
            ch_item = QTableWidgetItem("0")
            ch_item.setFlags(ch_item.flags() & ~Qt.ItemIsEditable)
            ch_item.setTextAlignment(Qt.AlignCenter)
            self.prof_stats_table.setItem(0, 0, ch_item)
            mi = QTableWidgetItem(f"{mean_v:.4f}")
            mi.setTextAlignment(Qt.AlignCenter)
            si = QTableWidgetItem(f"{std_v:.4f}")
            si.setTextAlignment(Qt.AlignCenter)
            mdi = QTableWidgetItem(f"{int(median_v)}" if is_int_dtype else f"{median_v:.4f}")
            mdi.setTextAlignment(Qt.AlignCenter)
            mini = QTableWidgetItem(f"{int(min_v)}" if is_int_dtype else f"{min_v:.4f}")
            mini.setTextAlignment(Qt.AlignCenter)
            maxi = QTableWidgetItem(f"{int(max_v)}" if is_int_dtype else f"{max_v:.4f}")
            maxi.setTextAlignment(Qt.AlignCenter)
            self.prof_stats_table.setItem(0, 1, mi)
            self.prof_stats_table.setItem(0, 2, si)
            self.prof_stats_table.setItem(0, 3, mdi)
            self.prof_stats_table.setItem(0, 4, mini)
            self.prof_stats_table.setItem(0, 5, maxi)
            for col in range(1, 6):
                item = self.prof_stats_table.item(0, col)
                if item is not None:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
