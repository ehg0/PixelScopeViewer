"""modeless な子 window の共通処理（最小化・位置の記憶・前面表示・親との連動）。"""

import contextlib
from collections.abc import Callable

from PySide6.QtCore import QByteArray, QEvent, QPoint, Qt
from PySide6.QtWidgets import QDialog, QWidget


def restore_from_minimized(w: QWidget) -> None:
    """最小化された w を、最小化前の状態（最大化または通常）に戻す。"""
    if w.windowState() & Qt.WindowMaximized:
        w.showMaximized()
    else:
        w.showNormal()


def bring_to_front(w: QWidget) -> None:
    """w を表示して前面に出す。最小化されていれば元に戻す。

    表示中の window に show() を再実行すると位置が変わることがあるため、非表示のときだけ show() を呼ぶ。
    """
    if w.isMinimized():
        restore_from_minimized(w)
    elif not w.isVisible():
        w.show()
    w.raise_()
    w.activateWindow()


class ToolDialog(QDialog):
    """最小化でき、最前面に固定しない modeless dialog の基底クラス。閉じると削除される。

    最小化前の位置を記憶し、復元時に戻す。remember_geometry が True の class は位置と大きさも記憶し、
    開き直したときに restore_geometry() で戻せる。記憶は window_key ごとに持ち、継承した class は共有する。
    maximizable が True の class は最大化もできる。
    """

    window_key = "tool"
    remember_geometry = False
    maximizable = False

    _saved_geometry: dict[str, QByteArray] = {}
    _position_before_minimize: dict[str, QPoint] = {}

    def __init__(self, parent=None):
        super().__init__(parent)
        # 表示後に flags を変えると window がいったん隠れ、位置が変わることがあるため、ここでだけ設定する
        flags = Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint
        if self.maximizable:
            flags |= Qt.WindowMaximizeButtonHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_DeleteOnClose)

    def restore_geometry(self) -> None:
        """記憶した位置と大きさに戻す。layout と初期サイズを設定した後に呼ぶ。"""
        saved = ToolDialog._saved_geometry.get(self.window_key)
        if saved:
            self.restoreGeometry(saved)

    def changeEvent(self, event):
        # 最小化前の位置を保存し、復元時に戻す
        if event.type() == QEvent.WindowStateChange:
            positions = ToolDialog._position_before_minimize
            if self.isMinimized():
                positions[self.window_key] = self.pos()
            elif event.oldState() & Qt.WindowMinimized and not self.isMaximized() and self.window_key in positions:
                self.move(positions[self.window_key])
        super().changeEvent(event)

    def moveEvent(self, event):
        if self.remember_geometry:
            ToolDialog._saved_geometry[self.window_key] = self.saveGeometry()
        super().moveEvent(event)

    def resizeEvent(self, event):
        if self.remember_geometry:
            ToolDialog._saved_geometry[self.window_key] = self.saveGeometry()
        super().resizeEvent(event)


class ChildDialogs:
    """親 window と最小化・復元・前面表示・close を連動させる子 dialog の一覧。

    親の changeEvent / mousePressEvent / closeEvent から、それぞれ対応するメソッドを呼ぶ。
    """

    def __init__(self):
        self._dialogs: list[QDialog] = []

    def track(self, dlg: QDialog, on_closed: Callable[[], None]) -> QDialog:
        """dlg を一覧に加える。閉じたら一覧から外し、on_closed を呼ぶ。"""
        self._dialogs.append(dlg)

        def closed():
            if dlg in self._dialogs:
                self._dialogs.remove(dlg)
            on_closed()

        dlg.finished.connect(closed)
        return dlg

    def _each(self, fn: Callable[[QDialog], None]) -> None:
        # 閉じると一覧から外れるため、copy を回す
        for dlg in list(self._dialogs):
            with contextlib.suppress(RuntimeError):  # Qt 側で削除済み
                fn(dlg)

    def sync_window_state(self, parent: QWidget, event: QEvent) -> None:
        """親の最小化・復元を子にも反映する。"""
        if event.type() != QEvent.WindowStateChange:
            return
        if parent.isMinimized():

            def apply(d):
                if d.isVisible() and not d.isMinimized():
                    d.showMinimized()

        elif event.oldState() & Qt.WindowMinimized:

            def apply(d):
                if d.isMinimized():
                    restore_from_minimized(d)

        else:
            return
        self._each(apply)

    def raise_visible(self) -> None:
        """表示中の子を前面に出す。"""

        def apply(d):
            if d.isVisible() and not d.isMinimized():
                d.raise_()

        self._each(apply)

    def close_all(self) -> None:
        """表示中の子をすべて閉じる。"""

        def apply(d):
            if d.isVisible():
                d.close()

        self._each(apply)
