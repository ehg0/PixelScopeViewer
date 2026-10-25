"""ImageViewer の ROI 一覧の管理（登録・削除・連動・JSON の保存と読み込み）。"""

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QFileDialog, QMessageBox

from PixelScopeViewer.core.roi_io import load_rois, save_rois
from PixelScopeViewer.ui.viewer.state import RoiEntry

_FILE_FILTER = "ROI list (*.json);;All Files (*.*)"


class RoiListManager:
    """viewer.state.rois を変更し、viewer.rois_changed で通知する。

    一覧で選択した ROI は編集中 ROI と連動し、編集中 ROI の変更がその ROI に反映される。
    """

    def __init__(self, viewer):
        self.viewer = viewer

    @property
    def _state(self):
        return self.viewer.state

    def enabled_rois(self) -> list[RoiEntry]:
        """解析対象（☑）の ROI を返す。"""
        return [e for e in self._state.rois if e.enabled]

    def find(self, roi_id: int) -> RoiEntry | None:
        return next((e for e in self._state.rois if e.id == roi_id), None)

    def _changed(self):
        self.viewer.image_label.update()
        self.viewer.rois_changed.emit()

    # --- 登録・削除 ---
    def add_current(self):
        """編集中 ROI を一覧の末尾に登録する。"""
        roi = self._state.roi
        if self._state.current_index is None or roi is None or roi.isEmpty():
            QMessageBox.information(self.viewer, "ROI一覧", "登録する ROI がありません。")
            return
        self._state.rois.append(RoiEntry(self._state.next_roi_id, QRect(roi)))
        self._state.next_roi_id += 1
        self._changed()

    def remove(self, roi_id: int):
        entry = self.find(roi_id)
        if entry is None:
            return
        self._state.rois.remove(entry)
        if self._state.linked_roi_id == roi_id:
            self._state.linked_roi_id = None
        # id は再利用しないが、残しても使われない色の個別設定は消す
        self._drop_color_overrides(entry.name)
        self._changed()

    def clear(self):
        """一覧を空にし、名前の連番と色の個別設定も初期化する。"""
        self._state.rois.clear()
        self._state.next_roi_id = 1
        self._state.linked_roi_id = None
        self._state.roi_color_overrides.clear()
        self._changed()

    def set_enabled(self, roi_id: int, enabled: bool):
        entry = self.find(roi_id)
        if entry is None or entry.enabled == enabled:
            return
        entry.enabled = enabled
        self._changed()

    def set_color_override(self, label: str, color: str | None):
        """ROI の曲線の色を個別に設定する。None の場合は個別設定を消す。"""
        if color is None:
            self._state.roi_color_overrides.pop(label, None)
        else:
            self._state.roi_color_overrides[label] = color
        self._changed()

    def reset_color_overrides(self, roi_id: int):
        """ROI の全 channel の色の個別設定を消し、パレットの色に戻す。"""
        if self._drop_color_overrides(f"R{roi_id}"):
            self._changed()

    def _drop_color_overrides(self, name: str) -> bool:
        overrides = self._state.roi_color_overrides
        labels = [k for k in overrides if k.startswith(f"{name} ")]
        for label in labels:
            del overrides[label]
        return bool(labels)

    # --- 編集中 ROI との連動 ---
    def link(self, roi_id: int | None):
        """roi_id の ROI を編集中 ROI に読み込み、以後の編集中 ROI の変更をその ROI に反映する。"""
        entry = self.find(roi_id) if roi_id is not None else None
        new_id = entry.id if entry is not None else None
        if new_id == self._state.linked_roi_id:
            return
        self._state.linked_roi_id = new_id
        if entry is not None:
            self.viewer.set_roi_from_image_rect(QRect(entry.rect))
        self._changed()

    def unlink(self):
        """連動を解除する。drag で新しい ROI を作り始めたときに呼ぶ。"""
        if self._state.linked_roi_id is not None:
            self._state.linked_roi_id = None
            self._changed()

    def sync_linked(self):
        """編集中 ROI を連動中の ROI に反映する。通知は編集中 ROI の変更の通知（roi_changed）に任せる。"""
        entry = self.find(self._state.linked_roi_id) if self._state.linked_roi_id is not None else None
        roi = self._state.roi
        if entry is not None and roi is not None and not roi.isEmpty():
            entry.rect = QRect(roi)

    # --- ファイル ---
    def save_dialog(self):
        """ファイル選択 dialog で選んだ JSON ファイルに ROI 一覧を保存する。"""
        if not self._state.rois:
            QMessageBox.information(self.viewer, "ROI一覧", "保存する ROI がありません。")
            return
        path, _ = QFileDialog.getSaveFileName(self.viewer, "ROI一覧を保存", "rois.json", _FILE_FILTER)
        if not path:
            return
        rois = [
            {
                "id": e.id,
                "x": e.rect.x(),
                "y": e.rect.y(),
                "width": e.rect.width(),
                "height": e.rect.height(),
                "enabled": e.enabled,
            }
            for e in self._state.rois
        ]
        try:
            save_rois(path, rois, self._state.roi_color_overrides)
        except OSError as e:
            QMessageBox.warning(self.viewer, "ROI一覧", f"保存できませんでした。\n{e}")

    def load_dialog(self):
        """ファイル選択 dialog で選んだ JSON ファイルの ROI 一覧で、今の一覧を置き換える。"""
        path, _ = QFileDialog.getOpenFileName(self.viewer, "ROI一覧を読み込み", "", _FILE_FILTER)
        if not path:
            return
        if self._state.rois:
            answer = QMessageBox.question(
                self.viewer, "ROI一覧", "今の ROI 一覧を、読み込んだ ROI 一覧で置き換えます。よろしいですか？"
            )
            if answer != QMessageBox.Yes:
                return
        self.load(path)

    def load(self, path: str) -> bool:
        """JSON ファイルの ROI 一覧で今の一覧を置き換える。失敗したら warning を表示して False を返す。"""
        try:
            rois, overrides = load_rois(path)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self.viewer, "ROI一覧", f"読み込めませんでした。\n{e}")
            return False
        self._state.rois = [
            RoiEntry(r["id"], QRect(r["x"], r["y"], r["width"], r["height"]), r["enabled"]) for r in rois
        ]
        self._state.next_roi_id = max((r["id"] for r in rois), default=0) + 1
        self._state.linked_roi_id = None
        self._state.roi_color_overrides = dict(overrides)
        self._changed()
        return True
