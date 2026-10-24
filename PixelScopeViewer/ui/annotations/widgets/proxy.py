"""読み込み済みの画像の行のみに絞り込む proxy model。"""

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel

from PixelScopeViewer.ui.annotations.widgets.tables import resolve_path


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

        src = self.sourceModel()
        # 画像を 1 枚も読み込んでいない場合は全行を表示する
        if not src._loaded_paths:
            return True
        fp = src.manager.get_value(source_row, "fullfilepath")
        # パスがない行は判定できないので表示する
        return not fp or resolve_path(fp) in src._loaded_paths
