#!/usr/bin/env python3
# pyside6_image_viewer.py
import sys
import os
from typing import List, Optional, Tuple
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QLabel,
    QFileDialog,
    QMenu,
    QStatusBar,
    QWidget,
    QVBoxLayout,
    QRubberBand,
    QMessageBox,
    QDialog,
    QTextEdit,
)
from PySide6.QtGui import QPixmap, QImage, QKeySequence, QGuiApplication, QAction, QActionGroup, QIcon
from PySide6.QtCore import Qt, QRect, QPoint, QSize

import numpy as np
from PIL import Image


# ---------------------------
# Helper: numpy <-> QImage
# ---------------------------
def numpy_to_qimage(arr: np.ndarray) -> QImage:
    """
    Convert numpy array (H x W) or (H x W x C) to QImage for display.
    Display will clip values to 0-255 and use 8-bit depth for QImage.
    """
    if arr is None:
        return QImage()
    a = np.asarray(arr)
    if a.ndim == 2:
        # grayscale
        disp = np.clip(a, 0, 255).astype(np.uint8)
        h, w = disp.shape
        img = QImage(disp.data, w, h, w, QImage.Format_Grayscale8)
        return img.copy()
    elif a.ndim == 3:
        h, w, c = a.shape
        if c == 3 or c == 4:
            disp = np.clip(a, 0, 255).astype(np.uint8)
            if c == 3:
                # RGB
                # QImage expects bytes in RGB888 with RGB order
                img = QImage(disp.data, w, h, 3 * w, QImage.Format_RGB888)
                return img.copy()
            else:
                # RGBA
                img = QImage(disp.data, w, h, 4 * w, QImage.Format_RGBA8888)
                return img.copy()
        else:
            # unexpected channel number, convert to grayscale
            gray = np.clip(a.mean(axis=2), 0, 255).astype(np.uint8)
            h, w = gray.shape
            img = QImage(gray.data, w, h, w, QImage.Format_Grayscale8)
            return img.copy()
    else:
        raise ValueError("Unsupported array shape for conversion to QImage")


def pil_to_numpy(path: str) -> np.ndarray:
    img = Image.open(path)
    arr = np.array(img)
    return arr


# ---------------------------
# Image display widget
# ---------------------------
class ImageLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        self.setMouseTracking(True)
        self._pixmap = QPixmap()
        self.scale = 1.0
        self.rubber = QRubberBand(QRubberBand.Rectangle, self)
        self.rubber_origin = QPoint()
        self.selection_rect: Optional[QRect] = None
        self.showing = False

    def set_qimage(self, qimg: QImage, scale: float = 1.0):
        self.scale = scale
        self._qimage = qimg
        if qimg.isNull():
            self._pixmap = QPixmap()
            self.setPixmap(self._pixmap)
            self.showing = False
            return
        pix = QPixmap.fromImage(qimg)
        if scale != 1.0:
            w = int(pix.width() * scale)
            h = int(pix.height() * scale)
            pix = pix.scaled(w, h, Qt.KeepAspectRatio)
        self._pixmap = pix
        self.setPixmap(self._pixmap)
        self.adjustSize()
        self.showing = True

    def clear(self):
        self._pixmap = QPixmap()
        self.setPixmap(self._pixmap)
        self.showing = False
        self.selection_rect = None
        self.rubber.hide()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.showing:
            self.rubber_origin = ev.pos()
            self.rubber.setGeometry(QRect(self.rubber_origin, QSize()))
            self.rubber.show()

    def mouseMoveEvent(self, ev):
        if self.showing:
            if not self.rubber.isHidden():
                rect = QRect(self.rubber_origin, ev.pos()).normalized()
                self.rubber.setGeometry(rect)
            # Let parent handle mouse pos mapping (we'll emit via callback)
            if hasattr(self.parent(), "on_mouse_move"):
                self.parent().on_mouse_move(ev.pos())

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton and self.showing:
            if not self.rubber.isHidden():
                rect = self.rubber.geometry()
                self.rubber.hide()
                self.selection_rect = rect
                if hasattr(self.parent(), "on_selection_changed"):
                    self.parent().on_selection_changed(rect)

    def get_selection_in_image_coords(self) -> Optional[QRect]:
        """Return selection rect in image (original image) coordinates (integers)."""
        if self.selection_rect is None:
            return None
        # scale factor mapping: widget coordinates -> image coordinates
        s = self.scale
        img_x = int(self.selection_rect.x() / s)
        img_y = int(self.selection_rect.y() / s)
        img_w = max(1, int(self.selection_rect.width() / s))
        img_h = max(1, int(self.selection_rect.height() / s))
        return QRect(img_x, img_y, img_w, img_h)

    def set_selection_full(self):
        if not self.showing:
            return
        w = self._pixmap.width()
        h = self._pixmap.height()
        self.selection_rect = QRect(0, 0, int(w), int(h))
        # show rubber band to indicate selection (scaled coords)
        self.rubber.setGeometry(self.selection_rect)
        self.rubber.show()
        if hasattr(self.parent(), "on_selection_changed"):
            self.parent().on_selection_changed(self.selection_rect)


# ---------------------------
# Help dialog
# ---------------------------
class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(480, 320)
        text = QTextEdit(self)
        text.setReadOnly(True)
        content = """Keyboard shortcuts:
- 全選択 : Ctrl + A
- 選択領域をコピー : Ctrl + C
- 次の画像 : n
- 前の画像 : b
- 拡大 : +
- 縮小 : -
- 左ビットシフト : <
- 右ビットシフト : >
"""
        text.setPlainText(content)
        layout = QVBoxLayout(self)
        layout.addWidget(text)


# ---------------------------
# Main Window
# ---------------------------
class ImageViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 Image Viewer")
        self.resize(1000, 700)

        # Data store: list of dicts {'path': str, 'array': np.ndarray}
        self.images: List[dict] = []
        self.current_index: Optional[int] = None
        self.scale = 1.0

        # Central widget
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        self.image_label = ImageLabel(self)
        layout.addWidget(self.image_label)

        # status bar
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status_filename = QLabel()
        self.status_index = QLabel()
        self.status_pixel = QLabel()
        self.status.addWidget(self.status_filename, 1)
        self.status.addWidget(self.status_index)
        self.status.addPermanentWidget(self.status_pixel)

        # Menus
        self.create_menus()

        # Accept drops
        self.setAcceptDrops(True)

        # Shortcuts via QAction already set in menu; also connect keyPressEvent fallback
        self._create_shortcuts()

        # initialize
        self.update_status()
        self.help_dialog = HelpDialog(self)

    # ---------------------------
    # Menu creation
    # ---------------------------
    def create_menus(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("ファイル")
        act_load = QAction("読み込み...", self)
        act_load.triggered.connect(self.open_files)
        file_menu.addAction(act_load)

        act_select_all = QAction("全選択", self)
        act_select_all.setShortcut(QKeySequence("Ctrl+A"))
        act_select_all.triggered.connect(self.select_all)
        file_menu.addAction(act_select_all)

        act_copy_sel = QAction("選択領域をコピー", self)
        act_copy_sel.setShortcut(QKeySequence("Ctrl+C"))
        act_copy_sel.triggered.connect(self.copy_selection_to_clipboard)
        file_menu.addAction(act_copy_sel)

        # Image menu
        img_menu = menubar.addMenu("画像")
        act_next = QAction("次の画像", self)
        act_next.setShortcut(QKeySequence("n"))
        act_next.triggered.connect(self.next_image)
        img_menu.addAction(act_next)

        act_prev = QAction("前の画像", self)
        act_prev.setShortcut(QKeySequence("b"))
        act_prev.triggered.connect(self.prev_image)
        img_menu.addAction(act_prev)

        act_close = QAction("画像を閉じる", self)
        act_close.triggered.connect(self.close_current_image)
        img_menu.addAction(act_close)

        img_menu.addSeparator()
        # Placeholder for dynamic list of images
        self.image_list_menu = img_menu

        # View menu
        view_menu = menubar.addMenu("表示")
        act_zoom_in = QAction("拡大", self)
        act_zoom_in.setShortcut(QKeySequence("+"))
        act_zoom_in.triggered.connect(lambda: self.set_zoom(self.scale * 2.0))
        view_menu.addAction(act_zoom_in)

        act_zoom_out = QAction("縮小", self)
        act_zoom_out.setShortcut(QKeySequence("-"))
        act_zoom_out.triggered.connect(lambda: self.set_zoom(max(0.125, self.scale / 2.0)))
        view_menu.addAction(act_zoom_out)

        act_shift_left = QAction("左ビットシフト", self)
        act_shift_left.setShortcut(QKeySequence("<"))
        act_shift_left.triggered.connect(lambda: self.bit_shift(-1))
        view_menu.addAction(act_shift_left)

        act_shift_right = QAction("右ビットシフト", self)
        act_shift_right.setShortcut(QKeySequence(">"))
        act_shift_right.triggered.connect(lambda: self.bit_shift(1))
        view_menu.addAction(act_shift_right)

        # Analysis menu (buttons only - do nothing)
        analysis_menu = menubar.addMenu("解析")
        a1 = QAction("差分画像表示", self)
        analysis_menu.addAction(a1)
        a2 = QAction("プロファイル", self)
        analysis_menu.addAction(a2)
        a3 = QAction("ヒストグラム", self)
        analysis_menu.addAction(a3)

        # Help menu
        help_menu = menubar.addMenu("ヘルプ")
        act_help = QAction("キーボードショートカット", self)
        act_help.triggered.connect(self.show_help)
        help_menu.addAction(act_help)

    def _create_shortcuts(self):
        # also enable '+' '-' '<' '>' via QShortcuts if menu shortcuts not triggered in some layouts
        pass  # menu actions have shortcuts already

    # ---------------------------
    # File / Drag & Drop
    # ---------------------------
    def open_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Open image files", "", "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp *.exr *.pfm);;All Files (*)"
        )
        if files:
            self.load_image_files(files)

    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        urls = ev.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        image_paths = [
            p
            for p in paths
            if os.path.splitext(p)[1].lower() in (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".exr", ".pfm")
        ]
        if image_paths:
            self.load_image_files(image_paths)

    # ---------------------------
    # Image loading / management
    # ---------------------------
    def load_image_files(self, paths: List[str]):
        for p in paths:
            try:
                arr = pil_to_numpy(p)
            except Exception as e:
                QMessageBox.warning(self, "読み込みエラー", f"ファイル {p} の読み込みに失敗しました:\n{e}")
                continue
            self.images.append({"path": os.path.abspath(p), "array": arr.copy()})
        if self.current_index is None and self.images:
            self.current_index = 0
        self.update_image_list_menu()
        self.show_current_image()

    def update_image_list_menu(self):
        # Remove previous image list actions (everything after "画像を閉じる" separator)
        # We'll rebuild by clearing and re-adding close + separator then the list
        menubar = self.menuBar()
        # Find the "画像" menu object and rebuild it
        img_menu = None
        for action in menubar.actions():
            if action.text() == "画像":
                img_menu = action.menu()
                break
        if img_menu is None:
            return
        # Clear items entirely and recreate (simpler)
        img_menu.clear()
        act_next = QAction("次の画像", self)
        act_next.setShortcut(QKeySequence("n"))
        act_next.triggered.connect(self.next_image)
        img_menu.addAction(act_next)
        act_prev = QAction("前の画像", self)
        act_prev.setShortcut(QKeySequence("b"))
        act_prev.triggered.connect(self.prev_image)
        img_menu.addAction(act_prev)
        act_close = QAction("画像を閉じる", self)
        act_close.triggered.connect(self.close_current_image)
        img_menu.addAction(act_close)
        img_menu.addSeparator()

        # Add enumerated image list
        group = QActionGroup(self)
        group.setExclusive(True)
        for idx, img in enumerate(self.images):
            fname = img["path"]
            base = os.path.basename(fname)
            act = QAction(base, self)
            act.setCheckable(True)
            act.triggered.connect(self.make_show_image_callback(idx))
            if idx == self.current_index:
                act.setChecked(True)
                # show a black circle icon to the left
                pix = QPixmap(12, 12)
                pix.fill(Qt.transparent)
                from PySide6.QtGui import QPainter, QColor

                p = QPainter(pix)
                p.setBrush(QColor(0, 0, 0))
                p.setPen(Qt.NoPen)
                p.drawEllipse(2, 2, 8, 8)
                p.end()
                act.setIcon(QIcon(pix))
            group.addAction(act)
            img_menu.addAction(act)

    def make_show_image_callback(self, idx: int):
        def fn():
            self.current_index = idx
            self.show_current_image()

        return fn

    def show_current_image(self):
        if self.current_index is None:
            self.image_label.clear()
            self.update_status()
            self.update_image_list_menu()
            return
        if not (0 <= self.current_index < len(self.images)):
            self.current_index = None
            self.image_label.clear()
            self.update_status()
            self.update_image_list_menu()
            return
        data = self.images[self.current_index]
        arr = data["array"]
        qimg = numpy_to_qimage(arr)
        # display at current scale (scale variable is per-viewer)
        self.image_label.set_qimage(qimg, scale=self.scale)
        self.update_status()
        self.update_image_list_menu()

    # ---------------------------
    # Navigation
    # ---------------------------
    def next_image(self):
        if not self.images:
            return
        if self.current_index is None:
            self.current_index = 0
        else:
            self.current_index = (self.current_index + 1) % len(self.images)
        self.show_current_image()

    def prev_image(self):
        if not self.images:
            return
        if self.current_index is None:
            self.current_index = 0
        else:
            self.current_index = (self.current_index - 1) % len(self.images)
        self.show_current_image()

    def close_current_image(self):
        if self.current_index is None:
            return
        del self.images[self.current_index]
        if not self.images:
            self.current_index = None
        else:
            # clamp index
            if self.current_index >= len(self.images):
                self.current_index = len(self.images) - 1
        self.show_current_image()

    # ---------------------------
    # Zoom & bit shift
    # ---------------------------
    def set_zoom(self, scale: float):
        if not self.images or self.current_index is None:
            self.scale = scale
            return
        self.scale = scale
        # Re-render display pixmap at new scale from original array
        arr = self.images[self.current_index]["array"]
        qimg = numpy_to_qimage(arr)
        self.image_label.set_qimage(qimg, scale=self.scale)
        # keep selection empty because coordinates changed
        self.image_label.selection_rect = None
        self.update_status()

    def bit_shift(self, dir: int):
        """
        dir: +1 right shift (>>), -1 left shift (<<)
        left bit shift increases value: << 1
        """
        if not self.images or self.current_index is None:
            return
        arr = self.images[self.current_index]["array"]
        # Work on integer arrays. If float, convert to int first.
        if np.issubdtype(arr.dtype, np.floating):
            arr = arr.astype(np.int64)
        # Choose safe dtype for shifting
        # operate on int64 to avoid overflow
        arr_i = arr.astype(np.int64)
        if dir > 0:
            arr_i = arr_i >> 1
        else:
            arr_i = arr_i << 1
        # store back (keep dtype as int64)
        self.images[self.current_index]["array"] = arr_i
        # update display
        qimg = numpy_to_qimage(arr_i)
        self.image_label.set_qimage(qimg, scale=self.scale)
        self.update_status()

    # ---------------------------
    # Selection and clipboard
    # ---------------------------
    def select_all(self):
        if not self.images or self.current_index is None:
            return
        # set selection to entire visible pixmap region (widget coords)
        self.image_label.set_selection_full()

    def on_selection_changed(self, rect: QRect):
        # we receive rect in widget coords; convert and maybe show dims
        self.update_status()

    def copy_selection_to_clipboard(self):
        if not self.images or self.current_index is None:
            return
        sel = self.image_label.get_selection_in_image_coords()
        arr = self.images[self.current_index]["array"]
        if sel is None:
            QMessageBox.information(self, "コピー", "選択領域がありません。")
            return
        x, y, w, h = sel.x(), sel.y(), sel.width(), sel.height()
        # clamp
        h_img, w_img = arr.shape[0], arr.shape[1]
        x = max(0, min(x, w_img - 1))
        y = max(0, min(y, h_img - 1))
        w = max(1, min(w, w_img - x))
        h = max(1, min(h, h_img - y))
        sub = arr[y : y + h, x : x + w].copy()
        qimg = numpy_to_qimage(sub)
        if qimg.isNull():
            QMessageBox.warning(self, "コピー失敗", "選択領域の画像作成に失敗しました。")
            return
        clipboard = QGuiApplication.clipboard()
        clipboard.setImage(qimg)
        QMessageBox.information(self, "コピー完了", "選択領域をクリップボードにコピーしました。")

    # ---------------------------
    # Mouse tracking for pixel info
    # ---------------------------
    def on_mouse_move(self, pos: QPoint):
        # pos is in widget coords (scaled)
        if self.current_index is None:
            self.status_pixel.setText("")
            return
        arr = self.images[self.current_index]["array"]
        s = self.scale
        # map to image coords
        ix = int(pos.x() / s)
        iy = int(pos.y() / s)
        h, w = arr.shape[0], arr.shape[1]
        if 0 <= ix < w and 0 <= iy < h:
            val = arr[iy, ix]
            # format values as ints
            if isinstance(val, np.ndarray) or np.ndim(val) > 0:
                val_str = "(" + ",".join(str(int(x)) for x in np.ravel(val)) + ")"
            else:
                try:
                    val_str = str(int(val))
                except Exception:
                    val_str = str(val)
            self.status_pixel.setText(f"x={ix} y={iy} val={val_str}")
        else:
            self.status_pixel.setText("")

    # ---------------------------
    # Status updates
    # ---------------------------
    def update_status(self):
        if self.current_index is None:
            self.status_filename.setText("No image")
            self.status_index.setText("")
            self.status_pixel.setText("")
            return
        p = self.images[self.current_index]["path"]
        base = os.path.basename(p)
        idx = self.current_index + 1
        total = len(self.images)
        self.status_filename.setText(base)
        self.status_index.setText(f"{idx}/{total}")

    # ---------------------------
    # Help
    # ---------------------------
    def show_help(self):
        self.help_dialog.show()

    # ---------------------------
    # Key events fallback (simple)
    # ---------------------------
    def keyPressEvent(self, ev):
        key = ev.key()
        if key == Qt.Key_N:
            self.next_image()
        elif key == Qt.Key_B:
            self.prev_image()
        elif key in (Qt.Key_Plus, Qt.Key_Equal):
            self.set_zoom(self.scale * 2.0)
        elif key == Qt.Key_Minus:
            self.set_zoom(max(0.125, self.scale / 2.0))
        elif key == Qt.Key_Comma and ev.modifiers() & Qt.ShiftModifier:
            # '<' typically Shift+Comma
            self.bit_shift(-1)
        elif key == Qt.Key_Period and ev.modifiers() & Qt.ShiftModifier:
            # '>' typically Shift+Period
            self.bit_shift(1)
        else:
            super().keyPressEvent(ev)


# ---------------------------
# Entry point
# ---------------------------
def main():
    app = QApplication(sys.argv)
    w = ImageViewer()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
