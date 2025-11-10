from PySide6.QtCore import QSortFilterProxyModel, QModelIndex, Qt
from pathlib import Path


class LoadedOnlyProxyModel(QSortFilterProxyModel):
    """Proxy model that can filter to show only loaded images."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loaded_only = False

    def set_loaded_only(self, enabled: bool):
        self._loaded_only = enabled

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if not super().filterAcceptsRow(source_row, source_parent):
            return False
        # If not filtering by loaded-only, accept all rows
        if not self._loaded_only:
            return True

        try:
            src = self.sourceModel()
            # The source model must have a `_loaded_paths` cache for this to work.
            loaded_paths = getattr(src, "_loaded_paths", None)
            if loaded_paths is None:
                # If the model doesn't support our expected cache, accept the row
                # to avoid incorrectly hiding it.
                return True

            # If there are no loaded images at all, show all rows.
            if not loaded_paths:
                return True

            fp = src.manager.get_value(source_row, "fullfilepath")
            if not fp:
                # If there's no filepath, we can't determine if it's loaded,
                # so we don't filter it out.
                return True

            p = str(Path(str(fp)).resolve())
            return p in loaded_paths
        except Exception:
            # On any error, accept the row to be safe.
            pass
        return True
