"""タイトル行・画像・ステータス行を持つ画像の表示枠。"""

from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout

from PixelScopeViewer.ui.common import theme
from PixelScopeViewer.ui.viewer.widgets.image_label import ImageLabel


class ImagePane(QFrame):
    """scroll area の中の ImageLabel と、その上下のタイトル行（ファイル名）・ステータス行（pixel 値）。

    1 枚表示も 1×1 のタイルと同じ並びにし、枠線だけ付けない。
    scroll と viewport の resize は viewer.on_pane_view_changed に通知する。

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
        """1 枚表示では枠線を透明にする（画像の位置は変えない）。タイル比較モードの枠線は set_active で付ける。"""
        if not tile_mode:
            self.setStyleSheet(theme.TILE_SINGLE_FRAME_STYLESHEET)

    def show_image(self, img: dict | None, pixmap: QPixmap | None, scale: float, tile_number: int | None = None):
        """画像とファイル名を表示する。img が None の場合は空欄にする。

        Args:
            img: 画像の dict。
            pixmap: 表示用の QPixmap。
            scale: zoom 倍率。
            tile_number: タイル比較モードのタイル番号。タイトル行を "T{n}: ファイル名" にし、空欄は「（なし）」にする。
                1 枚表示は None にし、タイトル行をファイル名だけ（空欄は空）にする。
        """
        prefix = f"T{tile_number}: " if tile_number is not None else ""
        if img is None:
            self.image_id = None
            self.image_label.clear()
            self.title_label.setText(f"{prefix}（なし）" if prefix else "")
            self.title_label.setToolTip("")
            self.status_label.setText("")
            return
        self.image_id = img["id"]
        self.image_label.set_image(pixmap, scale)
        self.title_label.setText(f"{prefix}{Path(img['path']).name}")
        self.title_label.setToolTip(img["path"])

    def set_active(self, active: bool):
        """タイル比較モードの active タイルの枠を付ける。"""
        self.setStyleSheet(theme.TILE_ACTIVE_FRAME_STYLESHEET if active else theme.TILE_INACTIVE_FRAME_STYLESHEET)

    def eventFilter(self, obj, event):
        if obj is self.scroll_area.viewport() and event.type() == QEvent.Resize:
            self.viewer.on_pane_view_changed(self)
        return super().eventFilter(obj, event)
