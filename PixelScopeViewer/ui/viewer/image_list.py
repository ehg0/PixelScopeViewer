"""ImageViewer の画像一覧の管理（読み込み・切り替え・閉じる・画像 menu・差分画像）。"""

import contextlib
from collections.abc import Iterable
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox

from PixelScopeViewer.core.constants import STANDARD_IMAGE_EXTENSIONS
from PixelScopeViewer.core.image_io import ImageLoaderRegistry, load_image
from PixelScopeViewer.ui.common import theme
from PixelScopeViewer.ui.common.qt_image import numpy_to_qimage
from PixelScopeViewer.ui.diff import DiffDialog


class ImageListManager:
    """viewer.images（読み込んだ画像の dict のリスト）への追加・削除と、表示する画像の切り替えを行う。"""

    def __init__(self, viewer):
        self.viewer = viewer

    # --- 読み込み ---
    def open_files(self):
        """ファイル選択 dialog から画像を読み込む。"""
        registry = ImageLoaderRegistry.get_instance()
        custom_exts, has_wildcard = registry.get_supported_extensions()

        exts = [*STANDARD_IMAGE_EXTENSIONS, *sorted(set(custom_exts) - set(STANDARD_IMAGE_EXTENSIONS))]
        all_exts = " ".join(f"*{ext}" for ext in exts)

        # wildcard loader がある場合は "All Files" を既定の filter にする
        if has_wildcard:
            filter_str = f"All Files (*.*);;Images ({all_exts})"
        else:
            filter_str = f"Images ({all_exts});;All Files (*.*)"

        files, _ = QFileDialog.getOpenFileNames(self.viewer, "画像を開く", "", filter_str)
        self.add_and_show(files)

    def add_and_show(self, paths: Iterable[str]) -> int:
        """画像ファイルを読み込んで一覧に追加し、追加した画像の先頭を表示する。

        Returns:
            追加した画像の数。
        """
        new_count = self._load(paths)
        if new_count <= 0:
            return new_count
        state = self.viewer.state
        state.current_index = 0 if state.current_index is None else len(self.viewer.images) - new_count
        self.viewer.show_current_image()
        self.update_menu()
        return new_count

    def _load(self, paths: Iterable[str]) -> int:
        """画像ファイルを読み込んで images に追加する。

        loader が dict を返した場合は、各値を別の画像として追加する。

        Returns:
            追加した画像の数。
        """
        new_images = []
        failed_files = []

        for path in paths or []:
            if not path:
                continue
            try:
                load_data = load_image(path)

                # custom loader が対応できなかった場合
                if load_data is None:
                    failed_files.append((path, "カスタムローダーで処理できませんでした"))
                    continue

                path_str = str(Path(path).resolve())
                if not isinstance(load_data, dict):
                    entries = [(path_str, load_data)]
                else:
                    entries = [
                        (path_str if key in ("ORIGINAL", "ORIG", "SOURCE", "SRC") else f"{path_str}_{key}", arr)
                        for key, arr in load_data.items()
                    ]
                for entry_path, arr in entries:
                    img_data = self._make_entry(entry_path, arr, failed_files)
                    if img_data is not None:
                        new_images.append(img_data)

            except Exception as e:  # decoder・custom loader の失敗は様々なため、ファイルごとに記録してまとめて知らせる
                failed_files.append((path, str(e)))
                continue

        if failed_files:
            self._show_bulk_load_errors(failed_files)

        self.viewer.images.extend(new_images)
        return len(new_images)

    def _make_entry(self, path: str, arr: np.ndarray, failed_files: list) -> dict | None:
        """images に追加する dict を作成する。対応しない shape の場合は failed_files に追加して None を返す。"""
        if arr.ndim < 2 or arr.ndim > 3:
            failed_files.append((path, "2次元または3次元の配列が必要です"))
            return None
        if arr.ndim == 3 and arr.shape[2] not in [1, 2, 3, 4]:
            failed_files.append((path, "チャンネル数は1, 2, 3, または4である必要があります"))
            return None

        thumb_qimg = numpy_to_qimage(self.viewer.prepare_thumbnail_array(arr))
        thumb_pixmap = QPixmap.fromImage(thumb_qimg).scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return {"path": path, "array": arr, "base_array": arr.copy(), "thumbnail_pixmap": thumb_pixmap}

    def _show_load_error(self, path: str, arr=None, error_msg: str = ""):
        """ファイルの詳細を添えて読み込みエラーを表示する。"""
        filename = Path(path).name
        details = f"ファイル名: {filename}"
        if arr is not None:
            details += f"\n配列形状: {arr.shape}\nデータ型: {arr.dtype}"
        elif Path(path).suffix.lower() == ".npy":
            # 形状と dtype は補足情報のため、npy として読めない場合は省略する
            with contextlib.suppress(OSError, ValueError):
                arr = np.load(path)
                details += f"\n配列形状: {arr.shape}\nデータ型: {arr.dtype}"
        if error_msg:
            details += f"\n\nエラー: {error_msg}"
        QMessageBox.warning(self.viewer, "画像読み込みエラー", details)

    def _show_bulk_load_errors(self, failed_files):
        """複数ファイルの読み込みエラーをまとめて表示する。"""
        if len(failed_files) == 1:
            path, error = failed_files[0]
            self._show_load_error(path, error_msg=error)
            return

        msg = f"{len(failed_files)}個のファイルの読み込みに失敗しました:\n\n"
        for path, error in failed_files[:5]:  # 先頭 5 件のみ表示する
            filename = Path(path).name
            error_short = error if len(error) < 60 else error[:57] + "..."
            msg += f"• {filename}\n  {error_short}\n\n"

        if len(failed_files) > 5:
            msg += f"... 他 {len(failed_files) - 5} 件\n\n"

        msg += "\nヒント: カスタムローダーを登録することで対応できる可能性があります。\n"
        msg += "詳細は custom_loaders/README.md を参照してください。"

        QMessageBox.warning(self.viewer, "画像読み込みエラー", msg)

    # --- 切り替え ---
    def show_image(self, idx: int):
        """idx 番目の画像を表示する。"""
        self.viewer.state.current_index = idx
        if 0 <= idx < len(self.viewer.images):
            self.viewer.show_current_image()
        else:
            # 画像一覧が変わっている場合は menu を更新する
            self.update_menu()

    def next_image(self):
        if not self.viewer.images:
            return
        self.viewer.state.current_index = (self.viewer.state.current_index + 1) % len(self.viewer.images)
        self.viewer.show_current_image()

    def prev_image(self):
        if not self.viewer.images:
            return
        self.viewer.state.current_index = (self.viewer.state.current_index - 1) % len(self.viewer.images)
        self.viewer.show_current_image()

    def update_menu(self):
        """画像 menu を読み込み済みの画像一覧で更新する。"""
        v = self.viewer
        v.img_menu.clear()
        v.img_menu.addAction(v.next_image_action)
        v.img_menu.addAction(v.prev_image_action)
        v.img_menu.addSeparator()

        group = QActionGroup(v)
        group.setExclusive(True)
        for i, info in enumerate(v.images):
            act = QAction(info["path"], v)
            act.setCheckable(True)
            # triggered が発火しないよう、connect の前に check 状態と icon を設定する
            if i == v.state.current_index:
                act.setChecked(True)
                pix = QPixmap(12, 12)
                pix.fill(Qt.transparent)
                p = QPainter(pix)
                p.setBrush(QColor(theme.CURRENT_IMAGE_MARKER_COLOR))
                p.drawEllipse(2, 2, 8, 8)
                p.end()
                act.setIcon(QIcon(pix))
            act.triggered.connect(lambda _checked=False, i=i: self.show_image(i))
            group.addAction(act)
            v.img_menu.addAction(act)

    # --- 閉じる ---
    def close_current(self):
        """表示中の画像を閉じる。"""
        v = self.viewer
        if v.state.current_index is None:
            return
        # memory を解放するため配列を明示的に削除する
        img_data = v.images[v.state.current_index]
        img_data.pop("array", None)
        img_data.pop("base_array", None)
        del v.images[v.state.current_index]
        if not v.images:
            v.state.current_index = None
            v.image_label.clear()
        else:
            v.state.current_index = min(v.state.current_index, len(v.images) - 1)
        v.show_current_image()

    def close_all(self):
        """すべての画像を閉じる。"""
        v = self.viewer
        # memory を解放するため配列を明示的に削除する
        for img_data in v.images:
            img_data.pop("array", None)
            img_data.pop("base_array", None)
        v.images.clear()
        v.state.current_index = None
        v.image_label.clear()
        v.show_current_image()
        self.update_menu()
        # 開いている解析 dialog を空にする
        v._update_analysis_dialog()

    # --- 差分画像 ---
    def show_diff_dialog(self):
        """2 枚の画像の差分画像を作成して追加する。"""
        v = self.viewer
        if len(v.images) < 2:
            QMessageBox.information(v, "差分", "比較する画像が2枚必要です。")
            return
        dlg = DiffDialog(v, image_list=v.images, default_offset=127)
        if dlg.exec() != QDialog.Accepted:
            return
        a_idx, b_idx, offset = dlg.get_result()
        if a_idx is None or b_idx is None:
            return
        a = v.images[a_idx]["array"]
        b = v.images[b_idx]["array"]
        try:
            diff = a - b + offset
            diff[diff < 0] = 0
        except ValueError:
            QMessageBox.information(v, "差分", "差分の作成に失敗しました。画像サイズや型を確認してください。")
            return

        thumb_qimg = numpy_to_qimage(v.prepare_thumbnail_array(diff))
        thumb_pixmap = QPixmap.fromImage(thumb_qimg).scaled(
            v.navigator_widget.thumbnail_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        v.images.append(
            {
                "path": f"diff:{a_idx + 1}-{b_idx + 1}",
                "array": diff,
                "base_array": diff.copy(),
                "thumbnail_pixmap": thumb_pixmap,
            }
        )
        v.state.current_index = len(v.images) - 1
        v.show_current_image()
