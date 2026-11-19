"""続けて起きる更新を間引く部品。"""

from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer


class Throttle(QObject):
    """fn の実行を、続けて呼ばれても interval_ms に 1 回までにする。

    間隔が空いているときの呼び出しはすぐに実行する（単発の操作は遅れない）。
    間隔の途中に来た呼び出しはまとめて、間隔の終わりに 1 回だけ実行する（最後の状態は必ず反映される）。
    間隔は fn が終わってから数えるため、fn が重くても続けて実行されて操作が固まることはない。

    Args:
        fn: 間引いて実行する関数。実行する時点の状態を読む前提（引数は渡さない）。
        interval_ms: 実行の間隔の最小値。
        parent: 親の QObject。
    """

    def __init__(self, fn: Callable[[], None], interval_ms: int, parent: QObject | None = None):
        super().__init__(parent)
        self._fn = fn
        self._pending = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._on_timeout)

    def __call__(self):
        if self._timer.isActive():
            self._pending = True
            return
        self._run()

    def _run(self):
        self._pending = False
        self._fn()
        self._timer.start()

    def _on_timeout(self):
        if self._pending:
            self._run()
