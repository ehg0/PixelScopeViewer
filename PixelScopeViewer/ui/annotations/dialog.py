"""特徴量の表示・編集 dialog。"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMenu,
    QMenuBar,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableView,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from PixelScopeViewer.ui.annotations.model import AnnotationStore
from PixelScopeViewer.ui.annotations.widgets import (
    AnnotationsTableModel,
    ImageAnnotationsTableModel,
    LoadedOnlyProxyModel,
    PlainTextDelegate,
    SimpleDictTableModel,
)
from PixelScopeViewer.ui.annotations.widgets.tables import resolve_path
from PixelScopeViewer.ui.common import defaults
from PixelScopeViewer.ui.common.window import ToolDialog


class AnnotationsDialog(ToolDialog):
    """特徴量ファイルの images・categories・annotations を表示し、images を編集・保存する dialog。

    images の行を double click（または Enter）すると、対応する画像を viewer で表示する。
    """

    window_key = "annotations"

    def __init__(self, viewer, manager: AnnotationStore):
        super().__init__(viewer)
        self.viewer = viewer
        self.manager = manager
        self.update_title()
        self.resize(*defaults.FEATURES_DIALOG_SIZE)

        layout = QVBoxLayout(self)
        layout.setMenuBar(self._build_menu())
        layout.addLayout(self._build_controls())
        self._build_tabs()
        layout.addWidget(self.tabs, 1)

        self.filter_edit.textChanged.connect(self._on_filter_changed)
        self.filter_column.currentIndexChanged.connect(self._on_filter_col_changed)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.btn_add_col.clicked.connect(self._on_add_column)
        self.btn_save.clicked.connect(self._on_save)
        self.btn_toggle_cols.clicked.connect(self._on_toggle_columns)
        self.chk_show_loaded_only.toggled.connect(self._on_loaded_only_toggled)
        # 画像の変更時に強調表示と「読込済のみ」の絞り込みを更新する
        self.viewer.image_changed.connect(self._on_viewer_images_changed)

        self.refresh_filter_columns()
        self._on_filter_col_changed()
        self._on_tab_changed(0)

        self._apply_initial_sorts()

    # ----- UI 構築 -----
    def _build_menu(self) -> QMenuBar:
        menubar = QMenuBar(self)
        file_menu = QMenu("ファイル", self)
        act_open_annotations = file_menu.addAction("特徴量ファイルを開く…")
        act_open_annotations.triggered.connect(self._on_open_annotations)
        menubar.addMenu(file_menu)
        return menubar

    def _build_controls(self) -> QHBoxLayout:
        """filter と、列追加・保存・列表示・読み込みの設定を並べた行を作る。"""
        ctrl = QHBoxLayout()
        self.filter_edit = QLineEdit()
        self.filter_edit.setPlaceholderText("フィルタ文字列を入力…")
        self.filter_column = QComboBox()

        self.btn_add_col = QPushButton("列を追加")
        self.btn_save = QPushButton("保存…")
        self.btn_toggle_cols = QPushButton("列表示...")
        self.chk_load_unloaded = QCheckBox("未読み込みをロード")
        self.chk_load_unloaded.setChecked(True)
        self.chk_show_loaded_only = QCheckBox("読込済のみ")
        self.chk_show_loaded_only.setChecked(False)
        ctrl.addWidget(self.filter_column)
        ctrl.addWidget(self.filter_edit, 1)
        ctrl.addStretch(1)
        ctrl.addWidget(self.chk_show_loaded_only)
        ctrl.addWidget(self.chk_load_unloaded)
        ctrl.addWidget(self.btn_toggle_cols)
        ctrl.addWidget(self.btn_add_col)
        ctrl.addWidget(self.btn_save)
        return ctrl

    def _build_tabs(self):
        """images（編集可）・categories・annotations（読み取り専用）の table を tab に並べる。"""
        self.tabs = QTabWidget(self)

        self.model_images = ImageAnnotationsTableModel(self.viewer, self.manager)
        self.proxy_images = LoadedOnlyProxyModel(self)
        self.proxy_images.setSourceModel(self.model_images)
        self.proxy_images.setFilterCaseSensitivity(Qt.CaseInsensitive)
        # 大きなデータでは重いため、データ変更のたびに sort/filter し直さない
        self.proxy_images.setDynamicSortFilter(False)
        self.table_images = QTableView(self)
        self.table_images.setModel(self.proxy_images)
        self.table_images.setSortingEnabled(True)
        self.table_images.doubleClicked.connect(self._on_double_clicked)
        self.table_images.setSelectionBehavior(QTableView.SelectRows)
        self.table_images.setAlternatingRowColors(True)
        # 大きな table の描画を軽くする設定
        self.table_images.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table_images.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.table_images.setWordWrap(False)
        # 数値の列でも spin box を使わない
        self.table_images.setItemDelegate(PlainTextDelegate(self.table_images))
        self.table_images.verticalHeader().setVisible(False)
        self.table_images.horizontalHeader().setVisible(True)
        cols = self.manager.get_columns()
        if "id" in cols:
            self.table_images.setColumnWidth(cols.index("id"), 50)
        # 省略表示されたセルの tooltip を出す
        self.table_images.setMouseTracking(True)
        self._add_table_tab(self.table_images, "Images")

        self.model_categories = SimpleDictTableModel(
            self.manager.get_categories_rows, self.manager.get_categories_columns, editable=False
        )
        self.table_categories = self._make_readonly_table(self.model_categories)
        self._add_table_tab(self.table_categories, "Categories")

        self.model_annotations = AnnotationsTableModel(self.manager)
        self.table_annotations = self._make_readonly_table(self.model_annotations)
        self._add_table_tab(self.table_annotations, "Annotations")

    def _make_readonly_table(self, model) -> QTableView:
        table = QTableView(self)
        table.setModel(model.as_proxy(self))
        table.setSortingEnabled(True)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.setMouseTracking(True)
        return table

    def _add_table_tab(self, table: QTableView, title: str):
        w = QWidget(self)
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(table)
        self.tabs.addTab(w, title)

    # ----- UI handlers -----
    def refresh_from_manager(self):
        """AnnotationStore の内容を全 table に反映する。"""
        self.model_images.refresh()
        self.model_categories.refresh()
        self.model_annotations.refresh()
        self.refresh_filter_columns()
        self.refresh_roles()
        self._apply_initial_sorts()
        self.update_title()

    def update_title(self):
        """最後に読み込んだファイルを title に表示する。"""
        last_path = self.manager.get_last_loaded_path()
        self.setWindowTitle(f"特徴量表示 - {last_path}" if last_path else "特徴量表示")

    def _apply_initial_sorts(self):
        """各 table を key 列（images・categories は id、annotations は image_id）の昇順に並べる。"""
        for table, cols, key in (
            (self.table_images, self.manager.get_columns(), "id"),
            (self.table_categories, self.manager.get_categories_columns() or [], "id"),
            (self.table_annotations, self.model_annotations.get_columns(), "image_id"),
        ):
            if cols:
                key_col = cols.index(key) if key in cols else 0
                table.sortByColumn(key_col, Qt.AscendingOrder)
                table.horizontalHeader().setSortIndicator(key_col, Qt.AscendingOrder)

    def refresh_filter_columns(self):
        cols = self._current_columns()
        self.filter_column.blockSignals(True)
        self.filter_column.clear()
        self.filter_column.addItems(cols)
        self.filter_column.blockSignals(False)

    def refresh_roles(self):
        r = self.model_images.rowCount()
        c = self.model_images.columnCount()
        if r > 0 and c > 0:
            tl = self.model_images.index(0, 0)
            br = self.model_images.index(r - 1, c - 1)
            self.model_images.dataChanged.emit(tl, br, [Qt.DisplayRole, Qt.BackgroundRole, Qt.ForegroundRole])

    def _on_viewer_images_changed(self):
        self.proxy_images.invalidateFilter()
        self.refresh_roles()

    def _on_loaded_only_toggled(self, checked: bool):
        self.proxy_images.set_loaded_only(checked)
        self.proxy_images.invalidateFilter()

    def _on_open_annotations(self):
        files, _ = QFileDialog.getOpenFileNames(self, "特徴量ファイルを開く", "", "Feature Files (*.json *.csv)")
        if not files:
            return
        count = self.manager.load_annotation_files(files)
        if count <= 0:
            QMessageBox.information(self, "特徴量読み込み", "読み込めるデータがありませんでした。")
            return
        self.refresh_from_manager()

    def _on_toggle_columns(self):
        cols = self.manager.get_columns()
        fixed = {"id", "file_name"}
        available = [c for c in cols if c not in fixed]
        if not available:
            QMessageBox.information(self, "列表示", "表示切替可能な列がありません。")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("列表示設定")
        dlg.resize(*defaults.FEATURES_COLUMN_DIALOG_SIZE)

        scroll_area = QScrollArea(dlg)
        scroll_area.setWidgetResizable(True)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        checks = {}
        for c in available:
            chk = QCheckBox(c)
            chk.setChecked(not self.table_images.isColumnHidden(cols.index(c)))
            checks[c] = chk
            scroll_layout.addWidget(chk)

        scroll_area.setWidget(scroll_widget)

        main_layout = QVBoxLayout(dlg)
        main_layout.addWidget(scroll_area)

        reset_btn = QPushButton("Reset (全列表示)")
        clear_btn = QPushButton("Clear（全選択解除）")

        hbox = QHBoxLayout()
        hbox.addWidget(reset_btn)
        hbox.addWidget(clear_btn)
        hbox.addStretch(1)

        def on_reset():
            for chk in checks.values():
                chk.setChecked(True)

        def on_clear():
            for chk in checks.values():
                chk.setChecked(False)

        reset_btn.clicked.connect(on_reset)
        clear_btn.clicked.connect(on_clear)
        main_layout.addLayout(hbox)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)

        def on_ok():
            for c in available:
                self.table_images.setColumnHidden(cols.index(c), not checks[c].isChecked())
            dlg.accept()

        btns.accepted.connect(on_ok)
        btns.rejected.connect(dlg.reject)

        h_btns = QHBoxLayout()
        h_btns.addStretch(1)
        h_btns.addWidget(btns)
        h_btns.addStretch(1)
        main_layout.addLayout(h_btns)
        dlg.exec()

    def _on_add_column(self):
        name, ok = QInputDialog.getText(self, "列を追加", "列名を入力：")
        if ok and name:
            self.manager.add_column(name)
            self.model_images.refresh()
            self.refresh_filter_columns()

    def _on_save(self):
        start_dir = self.manager.get_last_loaded_directory() or ""
        path, sel = QFileDialog.getSaveFileName(self, "保存", start_dir, "JSON (*.json);;CSV (*.csv)")
        if not path:
            return
        try:
            if path.lower().endswith(".csv"):
                self.manager.save_to_csv(path)
            elif path.lower().endswith(".json"):
                self.manager.save_to_json(path)
            else:
                path_json = str(Path(path).with_suffix(".json"))
                self.manager.save_to_json(path_json)
            QMessageBox.information(self, "保存", "保存しました。")
        except Exception as e:  # 書き込み先・polars の失敗は様々なため、まとめて知らせる
            QMessageBox.critical(self, "保存エラー", str(e))

    def _on_filter_changed(self, text: str):
        proxy = self._current_proxy()
        proxy.setFilterFixedString(text)

    def _on_filter_col_changed(self):
        proxy = self._current_proxy()
        cols = self._current_columns()
        col_name = self.filter_column.currentText() or (cols[0] if cols else "")
        if col_name and col_name in cols:
            idx = cols.index(col_name)
            proxy.setFilterKeyColumn(idx)

    def _on_tab_changed(self, idx: int):
        # 列追加・保存・列表示・読込済のみは images tab でのみ有効
        enable = idx == 0
        self.btn_add_col.setEnabled(enable)
        self.btn_save.setEnabled(enable)
        self.btn_toggle_cols.setEnabled(enable)
        self.chk_show_loaded_only.setEnabled(enable)

    def _on_double_clicked(self, proxy_index: QModelIndex):
        if self.tabs.currentIndex() != 0:
            return
        if not proxy_index.isValid():
            return
        src_index = self.proxy_images.mapToSource(proxy_index)
        row = src_index.row()
        fp = self.manager.get_value(row, "fullfilepath")
        if not fp:
            return
        QTimer.singleShot(0, lambda fp=fp: self._open_image_by_fullpath(fp))

    def _open_image_by_fullpath(self, fp: str):
        p = Path(str(fp))
        if not p.exists():
            QMessageBox.information(self, "画像を開く", "ファイルが存在しません。")
            return
        match_idx = None
        target = resolve_path(p)
        for i, info in enumerate(self.viewer.images):
            if resolve_path(info.get("path", "")) == target:
                match_idx = i
                break

        if match_idx is not None:
            self.viewer.state.current_index = match_idx
            self.viewer.show_current_image()
            return

        if not self.chk_load_unloaded.isChecked():
            return
        # 読み込みの失敗は _add_images が error dialog で知らせる
        n = self.viewer._add_images([str(p)])
        self.viewer._finalize_image_addition(n)

    def _current_table(self) -> QTableView:
        return (self.table_images, self.table_categories, self.table_annotations)[self.tabs.currentIndex()]

    def _current_proxy(self):
        i = self.tabs.currentIndex()
        return [self.proxy_images, self.model_categories.proxy, self.model_annotations.proxy][i]

    def _current_columns(self) -> list[str]:
        i = self.tabs.currentIndex()
        if i == 0:
            return self.manager.get_columns()
        elif i == 1:
            return self.manager.get_categories_columns() or []
        else:
            return self.model_annotations.get_columns()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self._current_table().clearSelection()
            event.accept()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # 選択行の画像を開く
            i = self.tabs.currentIndex()
            if i == 0:
                selection = self.table_images.selectionModel()
                if selection and selection.hasSelection():
                    indexes = selection.selectedRows()
                    if indexes:
                        proxy_index = indexes[0]
                        self._on_double_clicked(proxy_index)
                        event.accept()
                        return
            super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)
