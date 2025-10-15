#!/usr/bin/env python3
"""
PySide6 Image Viewer

仕様:
- メニューバー: ファイル, 画像, 表示, 解析, ヘルプ
- ファイル->読み込み: エクスプローラから複数画像読み込み
- ドラッグ&ドロップで画像読み込み
- 読み込んだ画像の1枚を等倍で表示 (スクロール可能)
- 画像バー: 次の画像, 前の画像, 画像を閉じる, 区切り線, 読み込んだ画像のフルパスを列挙
  - ビューワに表示されている画像の左には黒丸を表示
- 表示バー: 拡大(2x), 縮小(0.5x)
- 解析: プロファイル, ヒストグラム (ボタンだけ。未実装)
- ショートカット: 次(n), 前(b), 拡大(+), 縮小(-)
- ヘルプ: ショートカット別画面表示

使い方:
$ pip install PySide6
$ python pyside6_image_viewer.py
"""

import sys
import os
from PySide6 import QtCore, QtGui, QtWidgets


class ImageViewer(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Image Viewer (PySide6)")
        self.resize(1000, 700)

        # Model
        self.image_paths = []  # list of full paths
        self.current_index = -1
        self.original_pixmap = None
        self.zoom = 1.0

        # Central: scroll area with QLabel for pixmap
        self.image_label = QtWidgets.QLabel()
        self.image_label.setBackgroundRole(QtGui.QPalette.Base)
        self.image_label.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.image_label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop)

        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidget(self.image_label)
        self.scroll_area.setWidgetResizable(False)  # keep label at pixmap size (等倍)
        self.setCentralWidget(self.scroll_area)

        # Image bar (bottom): buttons + separator + list
        self._create_image_bar()

        # Menus and actions
        self._create_menus()

        # Shortcuts via actions (also appear in menus)
        self._create_shortcuts()

        # Drag & drop
        self.setAcceptDrops(True)

    def _create_image_bar(self):
        container = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(container)
        h.setContentsMargins(4, 4, 4, 4)
        h.setSpacing(8)

        btn_prev = QtWidgets.QPushButton("前の画像")
        btn_prev.clicked.connect(self.show_previous)
        btn_next = QtWidgets.QPushButton("次の画像")
        btn_next.clicked.connect(self.show_next)
        btn_close = QtWidgets.QPushButton("画像を閉じる")
        btn_close.clicked.connect(self.close_current_image)

        h.addWidget(btn_prev)
        h.addWidget(btn_next)
        h.addWidget(btn_close)

        # vertical separator (区切り線)
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.VLine)
        line.setFrameShadow(QtWidgets.QFrame.Sunken)
        h.addWidget(line)

        # list widget to show full paths
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.list_widget.itemClicked.connect(self.on_list_item_clicked)
        self.list_widget.setMinimumHeight(60)
        self.list_widget.setWrapping(False)
        self.list_widget.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        h.addWidget(self.list_widget, 1)

        # create a black circle pixmap used to mark current image
        self._make_circle_icon()

        dock = QtWidgets.QDockWidget("Images", self)
        dock.setWidget(container)
        dock.setAllowedAreas(QtCore.Qt.BottomDockWidgetArea | QtCore.Qt.TopDockWidgetArea)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, dock)

    def _make_circle_icon(self):
        size = 12
        pix = QtGui.QPixmap(size, size)
        pix.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pix)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        brush = QtGui.QBrush(QtCore.Qt.black)
        painter.setBrush(brush)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawEllipse(0, 0, size - 1, size - 1)
        painter.end()
        self.circle_icon = QtGui.QIcon(pix)

    def _create_menus(self):
        menubar = self.menuBar()

        # File
        file_menu = menubar.addMenu("ファイル")
        load_action = QtGui.QAction("読み込み", self)
        load_action.triggered.connect(self.load_images_dialog)
        file_menu.addAction(load_action)

        # Image
        image_menu = menubar.addMenu("画像")

        # View
        view_menu = menubar.addMenu("表示")
        zoom_in_action = QtGui.QAction("拡大 (2x)", self)
        zoom_in_action.triggered.connect(lambda: self.zoom_by(2.0))
        view_menu.addAction(zoom_in_action)
        zoom_out_action = QtGui.QAction("縮小 (0.5x)", self)
        zoom_out_action.triggered.connect(lambda: self.zoom_by(0.5))
        view_menu.addAction(zoom_out_action)

        # Analysis
        analysis_menu = menubar.addMenu("解析")
        profile_act = QtGui.QAction("プロファイル", self)
        profile_act.triggered.connect(lambda: None)  # 未実装
        hist_act = QtGui.QAction("ヒストグラム", self)
        hist_act.triggered.connect(lambda: None)  # 未実装
        analysis_menu.addAction(profile_act)
        analysis_menu.addAction(hist_act)

        # Help
        help_menu = menubar.addMenu("ヘルプ")
        help_act = QtGui.QAction("ショートカット", self)
        help_act.triggered.connect(self.show_help)
        help_menu.addAction(help_act)

        # store some actions for shortcuts
        self.action_next = QtGui.QAction("次の画像", self)
        self.action_next.triggered.connect(self.show_next)
        self.action_prev = QtGui.QAction("前の画像", self)
        self.action_prev.triggered.connect(self.show_previous)
        self.action_zoom_in = zoom_in_action
        self.action_zoom_out = zoom_out_action

    def _create_shortcuts(self):
        # assign single-key shortcuts
        self.action_next.setShortcut(QtGui.QKeySequence("n"))
        self.addAction(self.action_next)
        self.action_prev.setShortcut(QtGui.QKeySequence("b"))
        self.addAction(self.action_prev)
        self.action_zoom_in.setShortcut(QtGui.QKeySequence("+"))
        self.addAction(self.action_zoom_in)
        self.action_zoom_out.setShortcut(QtGui.QKeySequence("-"))
        self.addAction(self.action_zoom_out)

    def load_images_dialog(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(
            self, "画像を選択", os.path.expanduser("~"), "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff);;All files (*)"
        )
        if files:
            self.add_images(files)

    def add_images(self, paths):
        # normalize to absolute unique
        added = False
        for p in paths:
            fullp = os.path.abspath(p)
            if os.path.isfile(fullp) and fullp not in self.image_paths:
                self.image_paths.append(fullp)
                # append to list widget
                item = QtWidgets.QListWidgetItem(fullp)
                self.list_widget.addItem(item)
                added = True
        if added and self.current_index == -1 and len(self.image_paths) > 0:
            self.show_image_at_index(0)

    def dragEnterEvent(self, event: QtGui.QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event: QtGui.QDropEvent):
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        if paths:
            self.add_images(paths)

    def on_list_item_clicked(self, item: QtWidgets.QListWidgetItem):
        path = item.text()
        try:
            idx = self.image_paths.index(path)
        except ValueError:
            return
        self.show_image_at_index(idx)

    def show_image_at_index(self, idx: int):
        if idx < 0 or idx >= len(self.image_paths):
            self.current_index = -1
            self.original_pixmap = None
            self.image_label.clear()
            self._update_list_icons()
            return
        self.current_index = idx
        path = self.image_paths[idx]
        pix = QtGui.QPixmap(path)
        if pix.isNull():
            QtWidgets.QMessageBox.warning(self, "読み込み失敗", f"画像を開けません: {path}")
            return
        self.original_pixmap = pix
        self.zoom = 1.0
        self._apply_pixmap()
        # select item in list widget
        items = self.list_widget.findItems(path, QtCore.Qt.MatchExactly)
        if items:
            self.list_widget.setCurrentItem(items[0])
        self._update_list_icons()

    def _apply_pixmap(self):
        if self.original_pixmap is None:
            return
        target_size = self.original_pixmap.size() * self.zoom
        # ensure integer sizes
        target_size = QtCore.QSize(int(target_size.width()), int(target_size.height()))
        scaled = self.original_pixmap.scaled(target_size, QtCore.Qt.IgnoreAspectRatio, QtCore.Qt.SmoothTransformation)
        self.image_label.setPixmap(scaled)
        self.image_label.resize(scaled.size())

    def _update_list_icons(self):
        # clear icons then set icon for current
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            it.setIcon(QtGui.QIcon())
        if 0 <= self.current_index < len(self.image_paths):
            path = self.image_paths[self.current_index]
            items = self.list_widget.findItems(path, QtCore.Qt.MatchExactly)
            if items:
                items[0].setIcon(self.circle_icon)

    def show_next(self):
        if not self.image_paths:
            return
        if self.current_index < 0:
            self.show_image_at_index(0)
            return
        new = self.current_index + 1
        if new >= len(self.image_paths):
            new = 0
        self.show_image_at_index(new)

    def show_previous(self):
        if not self.image_paths:
            return
        if self.current_index < 0:
            self.show_image_at_index(0)
            return
        new = self.current_index - 1
        if new < 0:
            new = len(self.image_paths) - 1
        self.show_image_at_index(new)

    def close_current_image(self):
        if self.current_index < 0 or not self.image_paths:
            return
        removed = self.image_paths.pop(self.current_index)
        # remove from list widget
        items = self.list_widget.findItems(removed, QtCore.Qt.MatchExactly)
        for it in items:
            self.list_widget.takeItem(self.list_widget.row(it))
        # decide new index
        if self.current_index >= len(self.image_paths):
            self.current_index = len(self.image_paths) - 1
        if self.current_index >= 0:
            self.show_image_at_index(self.current_index)
        else:
            self.current_index = -1
            self.original_pixmap = None
            self.image_label.clear()
            self._update_list_icons()

    def zoom_by(self, factor: float):
        if self.original_pixmap is None:
            return
        self.zoom *= factor
        # clamp zoom to reasonable range
        self.zoom = max(0.125, min(16.0, self.zoom))
        self._apply_pixmap()

    def show_help(self):
        text = "キーボードショートカット:\n" "n : 次の画像\n" "b : 前の画像\n" "+ : 拡大 (2x)\n" "- : 縮小 (0.5x)\n"
        QtWidgets.QMessageBox.information(self, "ヘルプ - ショートカット", text)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    viewer = ImageViewer()
    viewer.show()
    sys.exit(app.exec())
