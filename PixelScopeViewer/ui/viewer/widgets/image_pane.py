"""タイトル行・画像・ステータス行を持つ画像の表示枠。"""

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout

from PixelScopeViewer.ui.common import theme
from PixelScopeViewer.ui.viewer.widgets.image_label import ImageLabel


class ImagePane(QFrame):
    """scroll area の中の ImageLabel と、その上下のタイトル行・ステータス行。

    1 枚表示ではタイトル行とステータス行を隠す。scroll と viewport の resize は viewer.on_pane_view_changed に通知する。

    Attributes:
        image_id: 表示中の画像の id。空欄の場合は None。
    """

    def __init__(self, viewer, parent=None):
        super().__init__(parent)
        self.viewer = viewer
        self.image_id: int | None = None
        self.setObjectName("tilePane")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.title_label = QLabel()
        self.title_label.setStyleSheet(theme.TILE_TITLE_STYLESHEET)
        self.title_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.title_label)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.image_label = ImageLabel(viewer, self)
        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area, 1)

        self.status_label = QLabel()
        self.status_label.setStyleSheet(theme.TILE_STATUS_ROW_STYLESHEET)
        layout.addWidget(self.status_label)

        self.scroll_area.horizontalScrollBar().valueChanged.connect(lambda _v: viewer.on_pane_view_changed(self))
        self.scroll_area.verticalScrollBar().valueChanged.connect(lambda _v: viewer.on_pane_view_changed(self))
        self.scroll_area.viewport().installEventFilter(self)

        self.set_tile_mode(False)

    def set_tile_mode(self, tile_mode: bool):
        """タイトル行・ステータス行の表示と枠線を切り替える。"""
        self.title_label.setVisible(tile_mode)
        self.status_label.setVisible(tile_mode)
        if not tile_mode:
            self.setStyleSheet("")

    def set_active(self, active: bool):
        """タイル比較モードの active タイルの枠を付ける。"""
        self.setStyleSheet(theme.TILE_ACTIVE_FRAME_STYLESHEET if active else theme.TILE_INACTIVE_FRAME_STYLESHEET)

    def eventFilter(self, obj, event):
        if obj is self.scroll_area.viewport() and event.type() == QEvent.Resize:
            self.viewer.on_pane_view_changed(self)
        return super().eventFilter(obj, event)
