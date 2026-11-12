"""Split 表示（登録 ROI・タイルごとのグラフを grid に並べる）の部品。"""

from collections.abc import Callable

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from PixelScopeViewer.ui.analysis.tabs.common import mouse_position_text, style_plot_item
from PixelScopeViewer.ui.common import theme

# Split のグラフの title。グラフが小さくなるため、編集中ROI・Overlay（12pt）より小さくする
SPLIT_TITLE_SIZE = "9pt"
# Split の Fit で 1 枚がこれより小さくなる場合は scroll bar を出す (幅, 高さ)
SPLIT_MIN_CELL = (160, 120)
# [-] で小さくできる 1 枚の下限 (幅, 高さ)
SPLIT_ZOOM_MIN_CELL = (80, 60)
SPLIT_ZOOM_STEP = 1.25
# Qt の QWIDGETSIZE_MAX（PySide6 からは import できない）
_WIDGET_SIZE_MAX = (1 << 24) - 1


class SplitPlotView(QWidget):
    """SplitPlotArea を scroll area に入れ、左上の [Fit] [+] [-] で grid の 1 枚の大きさを変える。

    Fit では表示エリアに合わせる。ただし 1 枚が SPLIT_MIN_CELL より小さくなる場合は scroll bar を出す。
    [+] [-]（グラフ上の Ctrl + wheel も同じ）では 1 枚の大きさを SPLIT_ZOOM_STEP 倍ずつ変え、
    表示エリアからはみ出す分は scroll する。グラフ上の中央 button の drag でも scroll できる。

    Args:
        source: grid・log の設定を共有する PlotItem。
        left_label: 縦軸の label。
        bottom_label: 横軸の label。
        on_status: マウス位置の値の文字列を受け取る callback。
    """

    def __init__(self, source: pg.PlotItem, left_label: str, bottom_label: str, on_status: Callable[[str], None]):
        super().__init__()
        self.area = SplitPlotArea(source, left_label, bottom_label, on_status)
        # None は Fit（表示エリアに合わせる）。それ以外は 1 枚の (幅, 高さ)
        self._cell_size: tuple[int, int] | None = None
        self._grid = (1, 1)  # (行数, 列数)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        buttons = QHBoxLayout()
        buttons.setSpacing(2)
        for text, tip, slot in (
            ("Fit", "グラフを表示エリアに合わせる", self.fit),
            ("+", "グラフを大きくする", lambda: self.zoom(SPLIT_ZOOM_STEP)),
            ("-", "グラフを小さくする", lambda: self.zoom(1 / SPLIT_ZOOM_STEP)),
        ):
            btn = QToolButton()
            btn.setText(text)
            btn.setToolTip(tip)
            btn.setMinimumWidth(28)
            btn.clicked.connect(slot)
            buttons.addWidget(btn)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setWidget(self.area)
        self.area.wheel_target = self.scroll.viewport()
        self.area.pan_target = self.scroll
        self.area.on_ctrl_wheel = self.zoom
        layout.addWidget(self.scroll, 1)
        self._apply_size()

    def plot_items(self, ids: list[int], n_cols: int) -> list[pg.PlotItem]:
        """SplitPlotArea.plot_items を呼び、行数・列数に合わせて grid の大きさを更新する。"""
        items = self.area.plot_items(ids, n_cols)
        grid = (max(1, -(-len(ids) // n_cols)), n_cols)
        if grid != self._grid:
            self._grid = grid
            self._apply_size()
        return items

    def fit(self):
        self._cell_size = None
        self._apply_size()

    def zoom(self, factor: float, anchor: QPoint | None = None):
        """1 枚の大きさを factor 倍にする。Fit 中は今の大きさを基準にする。

        Args:
            factor: 倍率。
            anchor: 拡大縮小の前後で表示エリア内の同じ位置に保つ点（SplitPlotArea の座標）。
        """
        rows, cols = self._grid
        old_w, old_h = self.area.width(), self.area.height()
        w, h = self._cell_size or (old_w / cols, old_h / rows)
        min_w, min_h = SPLIT_ZOOM_MIN_CELL
        self._cell_size = (max(min_w, round(w * factor)), max(min_h, round(h * factor)))
        self._apply_size()
        if anchor is None or not old_w or not old_h:
            return
        # anchor の点が wheel を回した位置に残るよう scroll する
        for bar, pos, old, new in (
            (self.scroll.horizontalScrollBar(), anchor.x(), old_w, self.area.width()),
            (self.scroll.verticalScrollBar(), anchor.y(), old_h, self.area.height()),
        ):
            in_view = pos - bar.value()
            bar.setValue(round(pos * new / old - in_view))

    def _apply_size(self):
        rows, cols = self._grid
        if self._cell_size is None:
            min_w, min_h = SPLIT_MIN_CELL
            self.area.setMinimumSize(cols * min_w, rows * min_h)
            self.area.setMaximumSize(_WIDGET_SIZE_MAX, _WIDGET_SIZE_MAX)
        else:
            w, h = self._cell_size
            self.area.setFixedSize(cols * w, rows * h)


class SplitPlotArea(pg.GraphicsView):
    """登録 ROI ごとの PlotItem を grid に並べる。

    PlotItem は ROI の id ごとに使い回し、ユーザーが設定した表示範囲を保つ。
    grid・log は source（編集中ROI・Overlay 用の PlotItem）の menu の設定に揃え、
    各 PlotItem の menu での変更は source に伝える。

    Args:
        source: grid・log の設定を共有する PlotItem。
        left_label: 縦軸の label。
        bottom_label: 横軸の label。
        on_status: マウス位置の値の文字列を受け取る callback。
    """

    _CTRL_CHECKS = ("xGridCheck", "yGridCheck", "logXCheck", "logYCheck")

    def __init__(self, source: pg.PlotItem, left_label: str, bottom_label: str, on_status: Callable[[str], None]):
        super().__init__()
        # pg.GraphicsLayoutWidget と同じ構成。GraphicsLayoutWidget は作るたびに mkQApp() を呼び、
        # PySide6 では QStyleHints への UniqueConnection の警告が出るため、直接組み立てる
        self.ci = pg.GraphicsLayout()
        self.setCentralItem(self.ci)
        self.setBackground(theme.PLOT_BACKGROUND)
        self._source = source
        self._labels = (left_label, bottom_label)
        self._items: dict[int, pg.PlotItem] = {}
        self._order: list[int] = []
        self._n_cols = 0
        # wheel を渡す widget（SplitPlotView の scroll area の viewport）
        self.wheel_target: QWidget | None = None
        # 中央 button の drag で scroll する scroll area（SplitPlotView の scroll area）
        self.pan_target: QScrollArea | None = None
        # Ctrl + wheel で呼ぶ callback（倍率, wheel の位置）
        self.on_ctrl_wheel: Callable[[float, QPoint], None] | None = None
        # 中央 button の drag の開始位置（global 座標）と、そのときの scroll 位置
        self._pan_start: tuple[QPoint, int, int] | None = None
        # None は軸の連動を設定し直す必要がある状態
        self._linked: bool | None = None
        self.scene().sigMouseMoved.connect(lambda pos: on_status(self._mouse_text(pos)))

    def plot_items(self, ids: list[int], n_cols: int) -> list[pg.PlotItem]:
        """ids の順に PlotItem を返す。

        ROI の増減か列数の変更があったときだけ、PlotItem を追加・削除して n_cols 列に並べ直す。
        """
        if ids != self._order or n_cols != self._n_cols:
            for item in list(self.ci.items):
                self.ci.removeItem(item)
            for roi_id in [r for r in self._items if r not in ids]:
                del self._items[roi_id]
            for n, roi_id in enumerate(ids):
                if roi_id not in self._items:
                    self._items[roi_id] = self._make_item()
                self.ci.addItem(self._items[roi_id], row=n // n_cols, col=n % n_cols)
            self._order = list(ids)
            self._n_cols = n_cols
            self._linked = None
        self.sync_controls()
        return [self._items[r] for r in ids]

    def _make_item(self) -> pg.PlotItem:
        item = pg.PlotItem()
        style_plot_item(item, *self._labels)
        for name in self._CTRL_CHECKS:
            getattr(item.ctrl, name).toggled.connect(
                lambda checked, n=name: getattr(self._source.ctrl, n).setChecked(checked)
            )
        return item

    def sync_controls(self):
        """各 PlotItem の grid・log を source に揃える。"""
        for item in self._items.values():
            for name in self._CTRL_CHECKS:
                getattr(item.ctrl, name).setChecked(getattr(self._source.ctrl, name).isChecked())

    def set_linked(self, linked: bool, series: list[tuple[np.ndarray, np.ndarray]]):
        """軸の連動を設定する。描画の後に呼ぶ。

        連動中は先頭の PlotItem の auto range に全 ROI のデータが収まるよう、
        全データの範囲を覆う透明な線を先頭の PlotItem に加える。
        連動を切り替えたときは auto range を有効に戻す。連動中は先頭の PlotItem だけを auto range にする。
        """
        items = [self._items[r] for r in self._order]
        if not items:
            return
        first = items[0]
        if linked != self._linked:
            first.setXLink(None)
            first.setYLink(None)
            for item in items[1:]:
                item.setXLink(first if linked else None)
                item.setYLink(first if linked else None)
                # 連動先の auto range は自身のデータだけに合わせ、先頭の範囲を上書きしてしまう
                if linked:
                    item.disableAutoRange()
                else:
                    item.enableAutoRange()
            first.enableAutoRange()
            self._linked = linked
        if linked and len(items) > 1:
            bounds = self._data_bounds(series)
            if bounds is not None:
                x0, x1, y0, y1 = bounds
                first.addItem(pg.PlotDataItem([x0, x1], [y0, y1], pen=pg.mkPen((0, 0, 0, 0))))

    def _data_bounds(self, series) -> tuple[float, float, float, float] | None:
        """全系列の (x 最小, x 最大, y 最小, y 最大) を返す。log 表示の軸では正の値だけを使う。"""
        log_x = self._source.ctrl.logXCheck.isChecked()
        log_y = self._source.ctrl.logYCheck.isChecked()
        xs_all, ys_all = [], []
        for xs, ys in series:
            xs = np.asarray(xs, dtype=float)
            ys = np.asarray(ys, dtype=float)
            keep = np.isfinite(xs) & np.isfinite(ys)
            if log_x:
                keep &= xs > 0
            if log_y:
                keep &= ys > 0
            xs_all.append(xs[keep])
            ys_all.append(ys[keep])
        if not xs_all:
            return None
        xs_all = np.concatenate(xs_all)
        ys_all = np.concatenate(ys_all)
        if xs_all.size == 0:
            return None
        return float(xs_all.min()), float(xs_all.max()), float(ys_all.min()), float(ys_all.max())

    def wheelEvent(self, event):
        # Ctrl + wheel はグラフの拡大縮小、それ以外は外側の scroll area の scroll に使う。
        # ViewBox は mouse が無効でも wheel を受け取って捨てるため、scene には渡さない
        if event.modifiers() & Qt.ControlModifier and self.on_ctrl_wheel is not None:
            delta = event.angleDelta().y() or event.angleDelta().x()
            if delta:
                self.on_ctrl_wheel(SPLIT_ZOOM_STEP ** (delta / 120), event.position().toPoint())
            event.accept()
            return
        if self.wheel_target is not None:
            QApplication.sendEvent(self.wheel_target, event)
        else:
            event.ignore()

    # 中央 button の drag で、外側の scroll area の表示位置を動かす
    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton and self.pan_target is not None:
            bars = (self.pan_target.horizontalScrollBar(), self.pan_target.verticalScrollBar())
            self._pan_start = (event.globalPosition().toPoint(), bars[0].value(), bars[1].value())
            self.viewport().setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._pan_start is not None:
            start, h, v = self._pan_start
            delta = event.globalPosition().toPoint() - start
            self.pan_target.horizontalScrollBar().setValue(h - delta.x())
            self.pan_target.verticalScrollBar().setValue(v - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton and self._pan_start is not None:
            self._pan_start = None
            self.viewport().unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _mouse_text(self, pos) -> str:
        for item in self._items.values():
            if item.sceneBoundingRect().contains(pos):
                return mouse_position_text(item, pos)
        return ""
