"""読み込み済みの画像の行のみに絞り込む proxy model。"""

from pathlib import Path

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel


class LoadedOnlyProxyModel(QSortFilterProxyModel):
    """読み込み済みの画像の行のみに絞り込める QSortFilterProxyModel。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loaded_only = False

    def set_loaded_only(self, enabled: bool):
        self._loaded_only = enabled

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not super().filterAcceptsRow(source_row, source_parent):
            return False
        if not self._loaded_only:
            return True

        try:
            src = self.sourceModel()
            # source model の _loaded_paths の cache を使う。cache がなければ絞り込まない
            loaded_paths = getattr(src, "_loaded_paths", None)
            if loaded_paths is None:
                return True

            # 画像を 1 枚も読み込んでいない場合は全行を表示する
            if not loaded_paths:
                return True

            fp = src.manager.get_value(source_row, "fullfilepath")
            if not fp:
                # パスがない行は判定できないので表示する
                return True

            p = str(Path(str(fp)).resolve())
            return p in loaded_paths
        except Exception:
            pass
        return True
