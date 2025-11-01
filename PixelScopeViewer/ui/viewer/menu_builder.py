"""Menu and keyboard shortcut configuration for ImageViewer.

This module handles the creation of all menus and application-level
keyboard shortcuts for the image viewer.
"""

from PySide6.QtGui import QAction
from PySide6.QtCore import Qt


def create_menus(viewer):
    """Create all menus and keyboard shortcuts for the viewer.

    Args:
        viewer: ImageViewer instance
    """
    menubar = viewer.menuBar()

    # File menu
    file_menu = menubar.addMenu("ファイル")
    file_menu.addAction(QAction("画像ファイルを開く...", viewer, shortcut="Ctrl+O", triggered=viewer.open_files))
    file_menu.addSeparator()
    file_menu.addAction(QAction("画像全体をROI", viewer, shortcut="Ctrl+A", triggered=viewer.select_all))
    file_menu.addAction(
        QAction("ROI領域の画像をコピー", viewer, shortcut="Ctrl+C", triggered=viewer.copy_roi_to_clipboard)
    )
    file_menu.addSeparator()
    file_menu.addAction(QAction("閉じる", viewer, shortcut="Ctrl+W", triggered=viewer.close_current_image))
    file_menu.addAction(QAction("すべて閉じる", viewer, shortcut="Ctrl+Shift+W", triggered=viewer.close_all_images))

    # Image menu
    viewer.img_menu = menubar.addMenu("画像")
    viewer.update_image_list_menu()

    # View menu
    view_menu = menubar.addMenu("表示")
    # Menu items with visual shortcut representation (wrap with lambda to ignore triggered(bool))
    view_menu.addAction(QAction("表示設定 (D)", viewer, triggered=lambda: viewer.show_brightness_dialog()))
    view_menu.addSeparator()
    view_menu.addAction(QAction("拡大", viewer, triggered=lambda: viewer.set_zoom(min(viewer.scale * 2, 128.0))))
    view_menu.addAction(QAction("縮小", viewer, triggered=lambda: viewer.set_zoom(max(viewer.scale / 2, 0.125))))

    # Analysis menu
    analysis = menubar.addMenu("解析")
    # Add visual shortcut representation for analysis dialog
    analysis.addAction(QAction("解析ダイアログ (A)", viewer, triggered=lambda: viewer.show_analysis_dialog()))
    analysis.addAction(QAction("メタデータ", viewer, triggered=lambda: viewer.show_analysis_dialog(tab="Metadata")))
    analysis.addAction(QAction("プロファイル", viewer, triggered=lambda: viewer.show_analysis_dialog(tab="Profile")))
    analysis.addAction(QAction("ヒストグラム", viewer, triggered=lambda: viewer.show_analysis_dialog(tab="Histogram")))
    analysis.addSeparator()
    analysis.addAction(QAction("特徴量表示 (T)", viewer, triggered=lambda: viewer.show_features_dialog()))
    analysis.addSeparator()
    analysis.addAction(QAction("差分画像表示", viewer, triggered=lambda: viewer.show_diff_dialog()))

    # Help menu
    help_menu = menubar.addMenu("ヘルプ")
    help_menu.addAction(QAction("キーボードショートカット", viewer, triggered=viewer.help_dialog.show))

    # Add global application-level shortcuts
    _create_global_shortcuts(viewer)


def _create_global_shortcuts(viewer):
    """Create application-level keyboard shortcuts.

    These shortcuts work even when dialogs are focused.

    Args:
        viewer: ImageViewer instance
    """
    # Next/Prev image shortcuts
    viewer.next_image_action = QAction(viewer)
    viewer.next_image_action.setShortcut("n")
    viewer.next_image_action.setShortcutContext(Qt.ApplicationShortcut)
    viewer.next_image_action.triggered.connect(viewer.next_image)
    viewer.addAction(viewer.next_image_action)

    viewer.prev_image_action = QAction(viewer)
    viewer.prev_image_action.setShortcut("b")
    viewer.prev_image_action.setShortcutContext(Qt.ApplicationShortcut)
    viewer.prev_image_action.triggered.connect(viewer.prev_image)
    viewer.addAction(viewer.prev_image_action)

    # Reset brightness shortcut
    viewer.reset_brightness_action = QAction(viewer)
    viewer.reset_brightness_action.setShortcut("Ctrl+R")
    viewer.reset_brightness_action.setShortcutContext(Qt.ApplicationShortcut)
    viewer.reset_brightness_action.triggered.connect(viewer.reset_brightness_settings)
    viewer.addAction(viewer.reset_brightness_action)

    # Gain adjustment shortcuts
    viewer.left_gain_adjust_action = QAction(viewer)
    viewer.left_gain_adjust_action.setShortcut("<")
    viewer.left_gain_adjust_action.setShortcutContext(Qt.ApplicationShortcut)
    viewer.left_gain_adjust_action.triggered.connect(lambda: viewer.adjust_gain_step(-1))
    viewer.addAction(viewer.left_gain_adjust_action)

    viewer.right_gain_adjust_action = QAction(viewer)
    viewer.right_gain_adjust_action.setShortcut(">")
    viewer.right_gain_adjust_action.setShortcutContext(Qt.ApplicationShortcut)
    viewer.right_gain_adjust_action.triggered.connect(lambda: viewer.adjust_gain_step(1))
    viewer.addAction(viewer.right_gain_adjust_action)

    # Fit zoom toggle shortcut
    viewer.fit_toggle_action = QAction(viewer)
    viewer.fit_toggle_action.setShortcut("f")
    viewer.fit_toggle_action.setShortcutContext(Qt.ApplicationShortcut)
    viewer.fit_toggle_action.triggered.connect(viewer.toggle_fit_zoom)
    viewer.addAction(viewer.fit_toggle_action)

    # Zoom shortcuts
    viewer.zoom_in_action = QAction(viewer)
    viewer.zoom_in_action.setShortcut("+")
    viewer.zoom_in_action.setShortcutContext(Qt.ApplicationShortcut)
    viewer.zoom_in_action.triggered.connect(lambda: viewer.set_zoom(min(viewer.scale * 2, 128.0)))
    viewer.addAction(viewer.zoom_in_action)

    viewer.zoom_out_action = QAction(viewer)
    viewer.zoom_out_action.setShortcut("-")
    viewer.zoom_out_action.setShortcutContext(Qt.ApplicationShortcut)
    viewer.zoom_out_action.triggered.connect(lambda: viewer.set_zoom(max(viewer.scale / 2, 0.125)))
    viewer.addAction(viewer.zoom_out_action)

    # Single-key shortcuts
    # D: Display settings (Display)
    viewer.show_display_settings_action = QAction(viewer)
    viewer.show_display_settings_action.setShortcut("D")
    viewer.show_display_settings_action.setShortcutContext(Qt.ApplicationShortcut)
    # Ignore QAction.triggered(bool) argument
    viewer.show_display_settings_action.triggered.connect(lambda checked=False: viewer.show_brightness_dialog())
    viewer.addAction(viewer.show_display_settings_action)

    # A: Analysis dialog (Analysis)
    viewer.show_analysis_action = QAction(viewer)
    viewer.show_analysis_action.setShortcut("A")
    viewer.show_analysis_action.setShortcutContext(Qt.ApplicationShortcut)
    # Wrap to ignore triggered(bool) argument that would incorrectly be passed as tab parameter
    viewer.show_analysis_action.triggered.connect(lambda checked=False: viewer.show_analysis_dialog())
    viewer.addAction(viewer.show_analysis_action)

    # F: Features dialog (Features)
    viewer.show_features_action = QAction(viewer)
    viewer.show_features_action.setShortcut("T")
    viewer.show_features_action.setShortcutContext(Qt.ApplicationShortcut)
    viewer.show_features_action.triggered.connect(lambda: viewer.show_features_dialog())
    viewer.addAction(viewer.show_features_action)
