import os
from typing import Optional
import numpy as np
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QScrollArea,
    QStatusBar,
    QLabel,
    QFileDialog,
    QMessageBox,
)
from PySide6.QtGui import QPixmap, QPainter, QIcon, QGuiApplication, QAction, QActionGroup
from PySide6.QtCore import Qt, QRect, QEvent

from .utils import numpy_to_qimage, pil_to_numpy, is_image_file
from .widgets import ImageLabel
from .dialogs import HelpDialog


class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 Image Viewer")
        self.resize(1000, 700)
        self.setMouseTracking(True)

        self.images = []
        self.current_index = None
        self.scale = 1.0

        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.current_selection_rect: Optional[QRect] = None

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.image_label = ImageLabel(self, self)
        self.scroll_area.setWidget(self.image_label)
        layout.addWidget(self.scroll_area)
        self.image_label.installEventFilter(self)

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status_filename = QLabel()
        self.status_index = QLabel()
        self.status_pixel = QLabel()
        self.status_selection = QLabel()
        self.status_shift = QLabel()
        self.status.addWidget(self.status_filename, 2)
        self.status.addWidget(self.status_index, 1)
        self.status.addPermanentWidget(self.status_pixel, 3)
        self.status.addPermanentWidget(self.status_selection, 2)
        self.status.addPermanentWidget(self.status_shift, 1)

        self.help_dialog = HelpDialog(self)

        self.create_menus()
        self.setAcceptDrops(True)

    def create_menus(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("ファイル")
        file_menu.addAction(QAction("読み込み...", self, triggered=self.open_files))
        file_menu.addAction(QAction("全選択", self, shortcut="Ctrl+A", triggered=self.select_all))
        file_menu.addAction(
            QAction("選択領域をコピー", self, shortcut="Ctrl+C", triggered=self.copy_selection_to_clipboard)
        )

        self.img_menu = menubar.addMenu("画像")
        self.update_image_list_menu()

        view_menu = menubar.addMenu("表示")
        view_menu.addAction(QAction("拡大", self, shortcut="+", triggered=lambda: self.set_zoom(self.scale * 2)))
        view_menu.addAction(
            QAction("縮小", self, shortcut="-", triggered=lambda: self.set_zoom(max(0.125, self.scale / 2)))
        )
        view_menu.addAction(QAction("左ビットシフト", self, shortcut="<", triggered=lambda: self.bit_shift(-1)))
        view_menu.addAction(QAction("右ビットシフト", self, shortcut=">", triggered=lambda: self.bit_shift(1)))

        analysis = menubar.addMenu("解析")
        for name in ["差分画像表示", "プロファイル", "ヒストグラム"]:
            analysis.addAction(QAction(name, self))

        help_menu = menubar.addMenu("ヘルプ")
        help_menu.addAction(QAction("キーボードショートカット", self, triggered=self.help_dialog.show))

    def open_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "画像を開く", "", "Images (*.png *.jpg *.tif *.bmp *.jpeg)")
        if files:
            for f in files:
                arr = pil_to_numpy(f)
                img_data = {"path": os.path.abspath(f), "array": arr, "base_array": arr.copy(), "bit_shift": 0}
                self.images.append(img_data)
            if self.current_index is None:
                self.current_index = 0
            self.show_current_image()
            self.update_image_list_menu()

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        files = [u.toLocalFile() for u in e.mimeData().urls()]
        image_files = [f for f in files if is_image_file(f)]
        if image_files:
            for f in image_files:
                arr = pil_to_numpy(f)
                img_data = {"path": os.path.abspath(f), "array": arr, "base_array": arr.copy(), "bit_shift": 0}
                self.images.append(img_data)
            if self.current_index is None:
                self.current_index = 0
            self.show_current_image()
            self.update_image_list_menu()

    def update_image_list_menu(self):
        self.img_menu.clear()
        self.img_menu.addAction(QAction("次の画像", self, shortcut="n", triggered=self.next_image))
        self.img_menu.addAction(QAction("前の画像", self, shortcut="b", triggered=self.prev_image))
        self.img_menu.addAction(QAction("画像を閉じる", self, triggered=self.close_current_image))
        self.img_menu.addSeparator()

        group = QActionGroup(self)
        group.setExclusive(True)
        for i, info in enumerate(self.images):
            act = QAction(info["path"], self)
            act.setCheckable(True)
            act.triggered.connect(self.make_show_callback(i))
            if i == self.current_index:
                act.setChecked(True)
                pix = QPixmap(12, 12)
                pix.fill(Qt.transparent)
                p = QPainter(pix)
                p.setBrush(Qt.black)
                p.drawEllipse(2, 2, 8, 8)
                p.end()
                act.setIcon(QIcon(pix))
            group.addAction(act)
            self.img_menu.addAction(act)

    def make_show_callback(self, idx):
        def fn():
            self.current_index = idx
            self.show_current_image()

        return fn

    def show_current_image(self):
        if self.current_index is None or not self.images:
            self.image_label.clear()
            self.update_status()
            return
        arr = self.images[self.current_index]["array"]
        self.display_image(arr)
        self.update_image_list_menu()

        if self.current_selection_rect:
            s = self.scale
            rect = QRect(
                int(self.current_selection_rect.x() * s),
                int(self.current_selection_rect.y() * s),
                int(self.current_selection_rect.width() * s),
                int(self.current_selection_rect.height() * s),
            )
            self.image_label.selection_rect = rect
            self.image_label.update()
            self.update_selection_status(rect)

    def display_image(self, arr):
        qimg = numpy_to_qimage(arr)
        self.image_label.set_qimage(qimg, self.scale)
        self.update_status()

    def next_image(self):
        if not self.images:
            return
        self.current_index = (self.current_index + 1) % len(self.images)
        self.show_current_image()

    def prev_image(self):
        if not self.images:
            return
        self.current_index = (self.current_index - 1) % len(self.images)
        self.show_current_image()

    def close_current_image(self):
        if self.current_index is None:
            return
        del self.images[self.current_index]
        if not self.images:
            self.current_index = None
        else:
            self.current_index = min(self.current_index, len(self.images) - 1)
        self.show_current_image()

    def set_zoom(self, scale: float):
        self.scale = scale
        if self.current_index is None:
            return
        arr = self.images[self.current_index]["array"]
        self.display_image(arr)

    def bit_shift(self, amount):
        if self.current_index is None:
            return
        img = self.images[self.current_index]
        base = img["base_array"]
        new_shift = img.get("bit_shift", 0) + amount
        if new_shift >= 0:
            shifted = np.clip(base.astype(np.int32) << new_shift, 0, 255).astype(np.uint8)
        else:
            shifted = np.clip(base.astype(np.int32) >> (-new_shift), 0, 255).astype(np.uint8)

        img["array"] = shifted
        img["bit_shift"] = new_shift
        self.display_image(shifted)
        self.status_shift.setText(f"Shift: {new_shift:+d}")

    def select_all(self):
        self.image_label.set_selection_full()

    def on_selection_changed(self, rect: QRect):
        s = self.scale
        self.current_selection_rect = QRect(
            int(rect.x() / s),
            int(rect.y() / s),
            int(rect.width() / s),
            int(rect.height() / s),
        )
        self.update_selection_status(rect)

    def copy_selection_to_clipboard(self):
        sel = self.current_selection_rect
        if not sel or self.current_index is None:
            QMessageBox.information(self, "コピー", "選択領域がありません。")
            return

        arr = self.images[self.current_index]["array"]
        x, y, w, h = sel.x(), sel.y(), sel.width(), sel.height()
        sub = arr[y : y + h, x : x + w]
        QGuiApplication.clipboard().setImage(numpy_to_qimage(sub))

    def eventFilter(self, obj, event):
        if obj is self.image_label and event.type() == QEvent.MouseMove:
            self.update_mouse_status(event.position().toPoint())
            return False
        return super().eventFilter(obj, event)

    def update_mouse_status(self, pos):
        if self.current_index is None or not self.images:
            self.status_pixel.setText("")
            return
        arr = self.images[self.current_index]["array"]
        s = self.scale if self.scale > 0 else 1.0
        ix = int(pos.x() / s)
        iy = int(pos.y() / s)
        h, w = arr.shape[:2]
        if 0 <= iy < h and 0 <= ix < w:
            v = arr[iy, ix]
            if np.ndim(v) == 0:
                val_str = str(int(v))
            else:
                val_str = "(" + ",".join(str(int(x)) for x in np.ravel(v)) + ")"
            self.status_pixel.setText(f"x={ix} y={iy} val={val_str}")
        else:
            self.status_pixel.setText("")

    def update_status(self):
        if self.current_index is None:
            self.status_filename.setText("No image")
            self.status_index.setText("")
            return
        p = self.images[self.current_index]["path"]
        self.status_filename.setText(p)
        self.status_index.setText(f"{self.current_index+1}/{len(self.images)}")

    def update_selection_status(self, rect=None):
        if rect is None or rect.isNull():
            self.status_selection.setText("")
            return
        s = self.scale if hasattr(self, "scale") else 1.0
        x0 = int(rect.left() / s)
        y0 = int(rect.top() / s)
        x1 = int(rect.right() / s)
        y1 = int(rect.bottom() / s)
        w = x1 - x0 + 1
        h = y1 - y0 + 1
        self.status_selection.setText(f"({x0}, {y0}) - ({x1}, {y1}), w: {w}, h: {h}")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.image_label.selection_rect = None
            self.image_label.update()
            self.status_selection.setText("")
            return
        super().keyPressEvent(e)
