"""マウスによる ROI の作成・移動・リサイズ。"""

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen

from PixelScopeViewer.ui.common import theme


class RoiManagerMixin:
    """マウス操作で ROI を扱う mixin。

    左 drag で作成、右 drag で移動、辺・角の左 drag でリサイズする。
    ROI は常に画像の pixel 境界に吸着する。
    """

    def __init_roi_manager__(self):
        self.roi_rect: QRect | None = None
        self.dragging = False
        self._moving = False
        self._resizing = False
        self._resize_edge = None  # 'left', 'right', 'top', 'bottom', 'tl', 'tr', 'bl', 'br'
        self.start_point = QPoint()
        self._start_img = None
        self._move_start_img = None
        self._move_orig_img_rect = None
        self._resize_start_img = None
        self._resize_orig_img_rect = None
        self._edge_grab_distance = 8  # リサイズ判定に使う辺からの距離（pixel）

    def _update_selection_rect_in_widget_coords(self, img_rect: QRect):
        """画像座標の矩形を widget 座標に変換して roi_rect に設定する。"""
        left = self._image_to_widget_x(img_rect.left())
        top = self._image_to_widget_y(img_rect.top())
        right_ex = self._image_to_widget_x(img_rect.left() + img_rect.width())
        bottom_ex = self._image_to_widget_y(img_rect.top() + img_rect.height())
        w = max(1, right_ex - left)
        h = max(1, bottom_ex - top)
        self.roi_rect = QRect(left, top, w, h)

    def _handle_resize_operation(self, cur_img):
        """画像座標のマウス位置 cur_img に合わせて ROI をリサイズする。"""
        if not (self._resize_start_img and self._resize_orig_img_rect):
            return

        orig = self._resize_orig_img_rect
        edge = self._resize_edge

        new_left = orig.left()
        new_top = orig.top()
        new_width = orig.width()
        new_height = orig.height()

        # 水平方向（左右の辺と角）
        if edge in ("left", "tl", "bl"):
            new_left_candidate = max(0, min(cur_img[0], orig.left() + orig.width() - 1))
            new_width = orig.left() + orig.width() - new_left_candidate
            new_left = new_left_candidate
        elif edge in ("right", "tr", "br"):
            new_right_candidate = max(orig.left(), min(cur_img[0], self._qimage.width() - 1))
            new_width = new_right_candidate - orig.left() + 1

        # 垂直方向（上下の辺と角）
        if edge in ("top", "tl", "tr"):
            new_top_candidate = max(0, min(cur_img[1], orig.top() + orig.height() - 1))
            new_height = orig.top() + orig.height() - new_top_candidate
            new_top = new_top_candidate
        elif edge in ("bottom", "bl", "br"):
            new_bottom_candidate = max(orig.top(), min(cur_img[1], self._qimage.height() - 1))
            new_height = new_bottom_candidate - orig.top() + 1

        new_width = max(1, new_width)
        new_height = max(1, new_height)
        new_rect = QRect(new_left, new_top, new_width, new_height)
        self._update_selection_rect_in_widget_coords(new_rect)

    def _handle_move_operation(self, cur_img):
        """画像座標のマウス位置 cur_img に合わせて ROI を移動する。"""
        if not (self._move_start_img and self._move_orig_img_rect):
            return

        orig = self._move_orig_img_rect
        dx = cur_img[0] - self._move_start_img[0]
        dy = cur_img[1] - self._move_start_img[1]

        new_x = max(0, min(orig.x() + dx, self._qimage.width() - orig.width()))
        new_y = max(0, min(orig.y() + dy, self._qimage.height() - orig.height()))
        new_rect = QRect(new_x, new_y, orig.width(), orig.height())
        self._update_selection_rect_in_widget_coords(new_rect)

    def _handle_create_operation(self, cur_img):
        """drag 開始点から画像座標のマウス位置 cur_img までの ROI を作成する。"""
        if not self._start_img:
            return

        x0 = min(self._start_img[0], cur_img[0])
        x1 = max(self._start_img[0], cur_img[0])
        y0 = min(self._start_img[1], cur_img[1])
        y1 = max(self._start_img[1], cur_img[1])
        new_rect = QRect(x0, y0, x1 - x0 + 1, y1 - y0 + 1)
        self._update_selection_rect_in_widget_coords(new_rect)

    def mousePressEvent(self, ev):
        if not self.showing:
            return

        self.start_point = ev.position().toPoint()
        edge = self._get_resize_edge(self.start_point)

        if ev.button() == Qt.LeftButton:
            if edge:
                self._resizing = True
                self._resize_edge = edge
                self._resize_start_img = self._widget_to_image_point(self.start_point)
                self._resize_orig_img_rect = self.get_roi_in_image_coords()
                self.dragging = True
            else:
                self._moving = False
                self._resizing = False
                self._start_img = self._widget_to_image_point(self.start_point)
                # クリック直後から 1 pixel の ROI を表示する
                if self._start_img is not None:
                    sx = self._image_to_widget_x(self._start_img[0])
                    sy = self._image_to_widget_y(self._start_img[1])
                    self.roi_rect = QRect(sx, sy, 1, 1)
                self.dragging = True
        elif ev.button() == Qt.RightButton and self.roi_rect and self.roi_rect.contains(self.start_point) and not edge:
            # ROI の内側（辺以外）を右クリックしたときのみ移動を開始する
            self._moving = True
            self._resizing = False
            self._move_start_img = self._widget_to_image_point(self.start_point)
            self._move_orig_img_rect = self.get_roi_in_image_coords()
            self.dragging = True

    def mouseMoveEvent(self, ev):
        # ROI の辺に hover したら cursor を変える
        if self.showing and not self.dragging and self.roi_rect:
            edge = self._get_resize_edge(ev.position().toPoint())
            self._update_cursor_for_edge(edge)

        if self.showing and self.dragging:
            cur_pt = ev.position().toPoint()
            cur_img = self._widget_to_image_point(cur_pt)
            if cur_img is None:
                return

            if self._resizing:
                self._handle_resize_operation(cur_img)
            elif self._moving:
                self._handle_move_operation(cur_img)
            else:
                self._handle_create_operation(cur_img)

            self.update()
            self._notify_roi_changed()

        # 親に画像範囲内へ clamp したマウス位置を通知する
        if hasattr(self.parent(), "on_mouse_move"):
            if self.showing and not self._orig_pixmap.isNull():
                disp_w = int(self._orig_pixmap.width() * self.scale)
                disp_h = int(self._orig_pixmap.height() * self.scale)
                p = ev.position().toPoint()
                p = QPoint(max(0, min(p.x(), max(0, disp_w - 1))), max(0, min(p.y(), max(0, disp_h - 1))))
                self.parent().on_mouse_move(p)
            else:
                self.parent().on_mouse_move(ev.position().toPoint())

    def mouseReleaseEvent(self, ev):
        if not self.showing:
            return

        if ev.button() == Qt.LeftButton:
            if self._resizing:
                self._resizing = False
                self._resize_edge = None
                self._resize_start_img = None
                self._resize_orig_img_rect = None
                self.dragging = False
                self.update()
                self._notify_roi_changed()
            else:
                self.dragging = False
                end_img = self._widget_to_image_point(ev.position().toPoint())
                if self._start_img is not None and end_img is not None:
                    self._handle_create_operation(end_img)
                self.update()
                self._notify_roi_changed()
        elif ev.button() == Qt.RightButton and self._moving:
            self._moving = False
            self._move_start_img = None
            self._move_orig_img_rect = None
            self.dragging = False
            self.update()
            self._notify_roi_changed()

    def paint_roi(self, painter: QPainter):
        """ROI の枠を描画する。"""
        if self.roi_rect and not self.roi_rect.isNull():
            pen = QPen(QColor(theme.ROI_COLOR), 1)
            painter.setPen(pen)
            painter.drawRect(self.roi_rect)

    def get_roi_in_image_coords(self) -> QRect | None:
        """ROI を画像座標で返す。ROI がない場合は None。"""
        if not self.roi_rect or self.roi_rect.isNull():
            return None
        return self._widget_rect_to_image(self.roi_rect)

    def set_roi_full(self):
        """画像全体を ROI にする。"""
        if not self.showing:
            return
        disp_w = int(self._orig_pixmap.width() * self.scale) if not self._orig_pixmap.isNull() else 0
        disp_h = int(self._orig_pixmap.height() * self.scale) if not self._orig_pixmap.isNull() else 0
        self.roi_rect = QRect(0, 0, max(1, disp_w), max(1, disp_h))
        self.update()

    def _get_resize_edge(self, pos: QPoint) -> str | None:
        """cursor 付近にある ROI の辺・角を返す。

        Returns:
            'tl', 'tr', 'bl', 'br', 'left', 'right', 'top', 'bottom' のいずれか。該当しない場合は None。
        """
        if not self.roi_rect or self.roi_rect.isNull():
            return None

        rect = self.roi_rect
        dist = self._edge_grab_distance

        # 小さな ROI でも右 drag で移動できる内側の領域が残るよう判定距離を縮める
        min_dimension = min(rect.width(), rect.height())
        if min_dimension < dist * 2:
            dist = max(1, min_dimension // 3)

        # 角を優先して判定する
        if abs(pos.x() - rect.left()) <= dist and abs(pos.y() - rect.top()) <= dist:
            return "tl"
        if abs(pos.x() - rect.right()) <= dist and abs(pos.y() - rect.top()) <= dist:
            return "tr"
        if abs(pos.x() - rect.left()) <= dist and abs(pos.y() - rect.bottom()) <= dist:
            return "bl"
        if abs(pos.x() - rect.right()) <= dist and abs(pos.y() - rect.bottom()) <= dist:
            return "br"

        if abs(pos.x() - rect.left()) <= dist and rect.top() <= pos.y() <= rect.bottom():
            return "left"
        if abs(pos.x() - rect.right()) <= dist and rect.top() <= pos.y() <= rect.bottom():
            return "right"
        if abs(pos.y() - rect.top()) <= dist and rect.left() <= pos.x() <= rect.right():
            return "top"
        if abs(pos.y() - rect.bottom()) <= dist and rect.left() <= pos.x() <= rect.right():
            return "bottom"

        return None

    def _update_cursor_for_edge(self, edge: str | None):
        if edge == "tl" or edge == "br":
            self.setCursor(Qt.SizeFDiagCursor)
        elif edge == "tr" or edge == "bl":
            self.setCursor(Qt.SizeBDiagCursor)
        elif edge == "left" or edge == "right":
            self.setCursor(Qt.SizeHorCursor)
        elif edge == "top" or edge == "bottom":
            self.setCursor(Qt.SizeVerCursor)
        else:
            self.setCursor(Qt.ArrowCursor)

    def _notify_roi_changed(self):
        if self.viewer and self.roi_rect and not self.roi_rect.isNull():
            self.viewer.on_roi_changed(self.roi_rect)
