from PySide6.QtCore import QSortFilterProxyModel, QModelIndex
from pathlib import Path


class LoadedOnlyProxyModel(QSortFilterProxyModel):
    """Proxy model that can filter to show only loaded images."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._viewer = None
        self._loaded_only = False

    def set_viewer(self, viewer):
        self._viewer = viewer

    def set_loaded_only(self, enabled: bool):
        self._loaded_only = enabled

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not super().filterAcceptsRow(source_row, source_parent):
            return False
        if not self._loaded_only or not self._viewer:
            return True
        try:
            fp_index = self.sourceModel().index(source_row, self.sourceModel()._columns.index("fullfilepath"))
            fp = self.sourceModel().data(fp_index)
            if not fp:
                return False
            p = Path(str(fp)).resolve()
            for info in self._viewer.images:
                if Path(info.get("path", "")).resolve() == p:
                    return True
        except Exception:
            pass
        return False
