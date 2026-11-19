"""画像送りの widget（メニューバー右端の ◀ 番号 ▶ と、画像 menu の画像一覧）。"""

from collections.abc import Callable

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtGui import QAction, QColor, QGuiApplication, QIcon, QPainter, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from PixelScopeViewer.ui.common import theme

# 画像一覧の高さの上限（行数）。これを超える分はスクロールして見る
IMAGE_LIST_MAX_ROWS = 20
# 画像一覧の幅の上限（画面の幅に対する割合）
IMAGE_LIST_MAX_WIDTH_RATIO = 0.6


class _JumpSpinBox(QSpinBox):
    """Enter で jump_requested、Esc とフォーカスが外れたときに canceled を出す番号欄。"""

    jump_requested = Signal(int)
    canceled = Signal()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.interpretText()
            self.jump_requested.emit(self.value())
            event.accept()
            return
        if event.key() == Qt.Key_Escape:
            self.canceled.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        # Enter を押さずに離れた場合はジャンプせず、今の番号の表示に戻す
        self.canceled.emit()
        super().focusOutEvent(event)


class ImageNavBar(QWidget):
    """◀ [番号] / 総数 ▶ の画像送り。番号は 1 始まりで表示し、Enter でその番号へジャンプする。

    Args:
        prev_action: 前の画像へ送る action（b）。
        next_action: 次の画像へ送る action（n）。
        return_focus: ジャンプ・取り消しの後に、フォーカスを画像へ戻す関数。
        parent: 親 widget。
    """

    # ジャンプ先の index（0 始まり）
    jump_requested = Signal(int)

    def __init__(
        self,
        prev_action: QAction,
        next_action: QAction,
        return_focus: Callable[[], None],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._return_focus = return_focus
        self._current = 0
        self._total = 0

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 6, 0)
        layout.setSpacing(2)

        self.prev_btn = self._arrow_button(prev_action, "◀")
        self.next_btn = self._arrow_button(next_action, "▶")

        self.spin = _JumpSpinBox()
        self.spin.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spin.setKeyboardTracking(False)
        self.spin.setAlignment(Qt.AlignRight)
        self.spin.setToolTip("番号を入力して Enter でジャンプ")
        self.spin.jump_requested.connect(self._on_jump)
        self.spin.canceled.connect(self._on_canceled)
        self.total_label = QLabel("/ 0")
        self.total_label.setContentsMargins(2, 0, 0, 0)
        # 番号欄の枠・内側の余白の幅（文字の幅を除いた分）
        opt_w = self.spin.minimumSizeHint().width() - self.spin.fontMetrics().horizontalAdvance(" ")
        self._spin_frame_w = max(opt_w, 16) + 4

        layout.addWidget(self.prev_btn)
        layout.addWidget(self.spin)
        layout.addWidget(self.total_label)
        layout.addWidget(self.next_btn)
        self.set_position(0, 0)

    def _arrow_button(self, action: QAction, symbol: str) -> QToolButton:
        btn = QToolButton(self)
        btn.setDefaultAction(action)
        # action の文字の代わりに記号だけを出し、tooltip に action の名前とショートカットを出す
        btn.setText(symbol)
        btn.setToolTip(f"{action.text()} ({action.shortcut().toString()})")
        btn.setAutoRaise(True)
        return btn

    def set_position(self, current: int, total: int):
        """表示する番号（current は 0 始まり）と総数を設定する。総数が 0 なら無効にする。"""
        self._current, self._total = current, total
        with_images = total > 0
        self.spin.blockSignals(True)
        if with_images:
            self.spin.setSpecialValueText("")
            self.spin.setRange(1, total)
            self.spin.setValue(min(current, total - 1) + 1)
        else:
            # 最小値のときに空欄を表示する
            self.spin.setRange(0, 0)
            self.spin.setSpecialValueText(" ")
        self.spin.blockSignals(False)
        # 総数の桁数に合わせて番号欄の幅を決める
        # 枠と内側の余白の分は、style が決める空の番号欄の幅から取る
        digits = len(str(max(total, 1)))
        text_w = self.spin.fontMetrics().horizontalAdvance("0" * max(digits, 2))
        self.spin.setFixedWidth(text_w + self._spin_frame_w)
        self.total_label.setText(f"/ {total}")
        for w in (self.prev_btn, self.next_btn, self.spin, self.total_label):
            w.setEnabled(with_images)
        self._relayout_in_parent()

    def _relayout_in_parent(self):
        """桁数が変わって幅が変わった場合に、親（メニューバー）に配置し直させる。

        QMenuBar は corner widget の大きさを resize のときにしか決め直さないため、同じ大きさの resize を送る。
        """
        parent = self.parentWidget()
        if parent is None or not self.isVisible() or self.width() == self.sizeHint().width():
            return
        QCoreApplication.sendEvent(parent, QResizeEvent(parent.size(), parent.size()))

    def _on_jump(self, number: int):
        if self._total > 0:
            self.jump_requested.emit(number - 1)
        self._return_focus()

    def _on_canceled(self):
        self.set_position(self._current, self._total)
        if self.spin.hasFocus():
            self._return_focus()


class _FilterEdit(QLineEdit):
    """↓ キーで一覧へ移る絞り込み欄。"""

    down_pressed = Signal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Down:
            self.down_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)


def _marker_icon(visible: bool) -> QIcon:
    """表示中の画像の印（●）。visible が False の場合は同じ大きさの透明な icon（行の文字の位置をそろえる）。"""
    pix = QPixmap(12, 12)
    pix.fill(Qt.transparent)
    if visible:
        p = QPainter(pix)
        p.setBrush(QColor(theme.CURRENT_IMAGE_MARKER_COLOR))
        p.drawEllipse(2, 2, 8, 8)
        p.end()
    return QIcon(pix)


class ImageListPopup(QWidget):
    """画像 menu に入れる、絞り込み欄と「番号: パス」の画像一覧。

    一覧の高さは IMAGE_LIST_MAX_ROWS 行までにし、それ以上はスクロールバーで見る。
    """

    # 選んだ画像の index（0 始まり）
    activated = Signal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.filter_edit = _FilterEdit()
        self.filter_edit.setPlaceholderText("絞り込み (番号・パス)")
        self.filter_edit.setClearButtonEnabled(True)
        self.filter_edit.textChanged.connect(self._apply_filter)
        self.filter_edit.returnPressed.connect(self._activate_first_visible)
        self.filter_edit.down_pressed.connect(self._focus_list)

        self.list = QListWidget()
        self.list.setTextElideMode(Qt.ElideMiddle)
        self.list.setUniformItemSizes(True)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.list.itemClicked.connect(self._on_item)
        self.list.itemActivated.connect(self._on_item)

        layout.addWidget(self.filter_edit)
        layout.addWidget(self.list)
        self._enabled = True

    def populate(self, paths: list[str], current: int | None, enabled: bool = True):
        """一覧を作り直す。current（0 始まり）の行に印を付けて選択し、見える位置に出す。

        Args:
            paths: 画像のパス。
            current: 表示中の画像の index。None の場合は印を付けない。
            enabled: False の場合は一覧の表示だけにし、選べないようにする（タイル比較モード）。
        """
        self._enabled = enabled
        self.filter_edit.blockSignals(True)
        self.filter_edit.clear()
        self.filter_edit.blockSignals(False)
        self.list.clear()
        marker, blank = _marker_icon(True), _marker_icon(False)
        for i, path in enumerate(paths):
            item = QListWidgetItem(marker if i == current else blank, f"{i + 1}: {path}")
            item.setToolTip(path)
            item.setData(Qt.UserRole, i)
            if not enabled:
                item.setFlags(item.flags() & ~(Qt.ItemIsEnabled | Qt.ItemIsSelectable))
            self.list.addItem(item)
        if not paths:
            self.list.addItem(QListWidgetItem("(画像がありません)"))
            self.list.item(0).setFlags(Qt.NoItemFlags)
        self._resize_to_contents()
        if current is not None and 0 <= current < len(paths):
            item = self.list.item(current)
            if enabled:
                self.list.setCurrentItem(item)
            self.list.scrollToItem(item, QListWidget.PositionAtCenter)

    def _resize_to_contents(self):
        n = self.list.count()
        row_h = self.list.sizeHintForRow(0) if n else self.list.fontMetrics().height()
        frame = 2 * self.list.frameWidth()
        self.list.setFixedHeight(min(max(n, 1), IMAGE_LIST_MAX_ROWS) * row_h + frame)

        texts = (self.list.item(i).text() for i in range(n))
        text_w = max((self.list.fontMetrics().horizontalAdvance(t) for t in texts), default=0)
        scrollbar_w = self.list.verticalScrollBar().sizeHint().width() if n > IMAGE_LIST_MAX_ROWS else 0
        width = text_w + self.list.iconSize().width() + scrollbar_w + frame + 24
        screen = self.screen() or QGuiApplication.primaryScreen()
        max_w = int(screen.availableGeometry().width() * IMAGE_LIST_MAX_WIDTH_RATIO) if screen else 1000
        self.list.setFixedWidth(min(max(width, 300), max_w))

    def _apply_filter(self, text: str):
        """text を含む行だけを表示する（大文字・小文字は区別しない）。"""
        key = text.strip().lower()
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(bool(key) and key not in item.text().lower())

    def _visible_rows(self) -> list[QListWidgetItem]:
        return [self.list.item(i) for i in range(self.list.count()) if not self.list.item(i).isHidden()]

    def _activate_first_visible(self):
        rows = self._visible_rows()
        if rows:
            self._on_item(rows[0])

    def _focus_list(self):
        rows = self._visible_rows()
        if rows and self._enabled:
            self.list.setCurrentItem(rows[0])
        self.list.setFocus()

    def _on_item(self, item: QListWidgetItem):
        index = item.data(Qt.UserRole)
        if self._enabled and index is not None:
            self.activated.emit(index)
