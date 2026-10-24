"""ImageViewer の menu と keyboard shortcut。"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction

from PixelScopeViewer.core.constants import MAX_ZOOM_SCALE, MIN_ZOOM_SCALE, ZOOM_STEP


def create_menus(viewer):
    """ImageViewer の menu と keyboard shortcut を作成する。"""
    menubar = viewer.menuBar()

    file_menu = menubar.addMenu("ファイル")
    file_menu.addAction(
        QAction("画像ファイルを開く...", viewer, shortcut="Ctrl+O", triggered=viewer.image_list.open_files)
    )
    file_menu.addSeparator()
    file_menu.addAction(QAction("画像全体をROI", viewer, shortcut="Ctrl+A", triggered=viewer.select_all))
    file_menu.addAction(
        QAction("ROI領域の画像をコピー", viewer, shortcut="Ctrl+C", triggered=viewer.copy_roi_to_clipboard)
    )
    file_menu.addSeparator()

    viewer.close_current_action = QAction("閉じる", viewer, shortcut="Ctrl+W")
    viewer.close_current_action.setShortcutContext(Qt.WindowShortcut)
    viewer.close_current_action.triggered.connect(viewer.image_list.close_current)
    viewer.addAction(viewer.close_current_action)
    file_menu.addAction(viewer.close_current_action)

    viewer.close_all_action = QAction("すべて閉じる", viewer, shortcut="Ctrl+Shift+W")
    viewer.close_all_action.setShortcutContext(Qt.WindowShortcut)
    viewer.close_all_action.triggered.connect(viewer.image_list.close_all)
    viewer.addAction(viewer.close_all_action)
    file_menu.addAction(viewer.close_all_action)

    file_menu.addSeparator()
    viewer.reboot_action = QAction("再起動", viewer)
    viewer.reboot_action.triggered.connect(viewer.reboot)
    viewer.addAction(viewer.reboot_action)
    file_menu.addAction(viewer.reboot_action)

    # 複数の menu と window shortcut で共用する action は、menu より先に作成する
    viewer.show_analysis_action = QAction("解析ビュー", viewer, shortcut="A")
    viewer.show_analysis_action.setShortcutContext(Qt.WindowShortcut)
    viewer.show_analysis_action.triggered.connect(lambda: viewer.show_analysis_dialog())
    viewer.addAction(viewer.show_analysis_action)

    viewer.show_display_settings_action = QAction("表示設定", viewer, shortcut="D")
    viewer.show_display_settings_action.setShortcutContext(Qt.WindowShortcut)
    viewer.show_display_settings_action.triggered.connect(lambda: viewer.brightness_manager.show_brightness_dialog())
    viewer.addAction(viewer.show_display_settings_action)

    viewer.show_annotations_action = QAction("特徴量表示", viewer, shortcut="T")
    viewer.show_annotations_action.setShortcutContext(Qt.WindowShortcut)
    viewer.show_annotations_action.triggered.connect(lambda: viewer.show_annotations_dialog())
    viewer.addAction(viewer.show_annotations_action)

    viewer.next_image_action = QAction("次の画像", viewer, shortcut="n")
    viewer.next_image_action.setShortcutContext(Qt.WindowShortcut)
    viewer.next_image_action.triggered.connect(viewer.image_list.next_image)
    viewer.addAction(viewer.next_image_action)

    viewer.prev_image_action = QAction("前の画像", viewer, shortcut="b")
    viewer.prev_image_action.setShortcutContext(Qt.WindowShortcut)
    viewer.prev_image_action.triggered.connect(viewer.image_list.prev_image)
    viewer.addAction(viewer.prev_image_action)

    viewer.zoom_in_action = QAction("拡大", viewer, shortcut="+")
    viewer.zoom_in_action.setShortcutContext(Qt.WindowShortcut)
    viewer.zoom_in_action.triggered.connect(
        lambda: viewer.zoom_manager.set_zoom(min(viewer.state.scale * ZOOM_STEP, MAX_ZOOM_SCALE))
    )
    viewer.addAction(viewer.zoom_in_action)

    viewer.zoom_out_action = QAction("縮小", viewer, shortcut="-")
    viewer.zoom_out_action.setShortcutContext(Qt.WindowShortcut)
    viewer.zoom_out_action.triggered.connect(
        lambda: viewer.zoom_manager.set_zoom(max(viewer.state.scale / ZOOM_STEP, MIN_ZOOM_SCALE))
    )
    viewer.addAction(viewer.zoom_out_action)

    # 画像 menu は画像移動の action を使うため、それらの作成後に作る
    viewer.img_menu = menubar.addMenu("画像")
    viewer.image_list.update_menu()

    view_menu = menubar.addMenu("表示")
    view_menu.addAction(viewer.show_display_settings_action)
    view_menu.addSeparator()
    view_menu.addAction(viewer.zoom_in_action)
    view_menu.addAction(viewer.zoom_out_action)

    analysis = menubar.addMenu("解析")
    analysis.addAction(viewer.show_analysis_action)
    analysis.addSeparator()
    analysis.addAction(viewer.show_annotations_action)
    analysis.addSeparator()
    analysis.addAction(QAction("差分画像表示", viewer, triggered=lambda: viewer.image_list.show_diff_dialog()))
    analysis.addAction(
        QAction("複数画像比較", viewer, shortcut="Shift+T", triggered=lambda: viewer.show_tiling_comparison_dialog())
    )

    help_menu = menubar.addMenu("ヘルプ")
    help_menu.addAction(QAction("ヘルプ / ショートカット", viewer, triggered=viewer.help_dialog.show))
    help_menu.addAction(QAction("現在の状態をコピー", viewer, triggered=viewer.copy_state_to_clipboard))

    _create_global_shortcuts(viewer)


def _create_global_shortcuts(viewer):
    """menu に表示しない keyboard shortcut を作成する。"""
    viewer.reset_brightness_action = QAction(viewer)
    viewer.reset_brightness_action.setShortcut("Ctrl+R")
    viewer.reset_brightness_action.setShortcutContext(Qt.WindowShortcut)
    viewer.reset_brightness_action.triggered.connect(viewer.brightness_manager.reset_brightness_settings)
    viewer.addAction(viewer.reset_brightness_action)

    viewer.left_gain_adjust_action = QAction(viewer)
    viewer.left_gain_adjust_action.setShortcut("<")
    viewer.left_gain_adjust_action.setShortcutContext(Qt.WindowShortcut)
    viewer.left_gain_adjust_action.triggered.connect(lambda: viewer.brightness_manager.adjust_gain_step(-1))
    viewer.addAction(viewer.left_gain_adjust_action)

    viewer.right_gain_adjust_action = QAction(viewer)
    viewer.right_gain_adjust_action.setShortcut(">")
    viewer.right_gain_adjust_action.setShortcutContext(Qt.WindowShortcut)
    viewer.right_gain_adjust_action.triggered.connect(lambda: viewer.brightness_manager.adjust_gain_step(1))
    viewer.addAction(viewer.right_gain_adjust_action)

    viewer.fit_toggle_action = QAction(viewer)
    viewer.fit_toggle_action.setShortcut("f")
    viewer.fit_toggle_action.setShortcutContext(Qt.WindowShortcut)
    viewer.fit_toggle_action.triggered.connect(viewer.zoom_manager.toggle_fit_zoom)
    viewer.addAction(viewer.fit_toggle_action)
