"""Menu and keyboard shortcut configuration for ImageViewer.

This module handles the creation of all menus and application-level
keyboard shortcuts for the image viewer.
"""

from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
from ...core.constants import MIN_ZOOM_SCALE, MAX_ZOOM_SCALE


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

    # Close actions with window-level shortcuts
    viewer.close_current_action = QAction("閉じる", viewer, shortcut="Ctrl+W")
    viewer.close_current_action.setShortcutContext(Qt.WindowShortcut)
    viewer.close_current_action.triggered.connect(viewer.close_current_image)
    viewer.addAction(viewer.close_current_action)
    file_menu.addAction(viewer.close_current_action)

    viewer.close_all_action = QAction("すべて閉じる", viewer, shortcut="Ctrl+Shift+W")
    viewer.close_all_action.setShortcutContext(Qt.WindowShortcut)
    viewer.close_all_action.triggered.connect(viewer.close_all_images)
    viewer.addAction(viewer.close_all_action)
    file_menu.addAction(viewer.close_all_action)

    # Create actions that will be used in multiple menus and as window shortcuts
    # These must be defined before menus that use them
    viewer.show_analysis_action = QAction("解析ダイアログ", viewer, shortcut="A")
    viewer.show_analysis_action.setShortcutContext(Qt.WindowShortcut)
    viewer.show_analysis_action.triggered.connect(lambda: viewer.show_analysis_dialog())
    viewer.addAction(viewer.show_analysis_action)

    viewer.show_display_settings_action = QAction("表示設定", viewer, shortcut="D")
    viewer.show_display_settings_action.setShortcutContext(Qt.WindowShortcut)
    viewer.show_display_settings_action.triggered.connect(lambda: viewer.show_brightness_dialog())
    viewer.addAction(viewer.show_display_settings_action)

    viewer.show_features_action = QAction("特徴量表示", viewer, shortcut="T")
    viewer.show_features_action.setShortcutContext(Qt.WindowShortcut)
    viewer.show_features_action.triggered.connect(lambda: viewer.show_features_dialog())
    viewer.addAction(viewer.show_features_action)

    # Image navigation actions
    viewer.next_image_action = QAction("次の画像", viewer, shortcut="n")
    viewer.next_image_action.setShortcutContext(Qt.WindowShortcut)
    viewer.next_image_action.triggered.connect(viewer.next_image)
    viewer.addAction(viewer.next_image_action)

    viewer.prev_image_action = QAction("前の画像", viewer, shortcut="b")
    viewer.prev_image_action.setShortcutContext(Qt.WindowShortcut)
    viewer.prev_image_action.triggered.connect(viewer.prev_image)
    viewer.addAction(viewer.prev_image_action)

    # Zoom actions
    viewer.zoom_in_action = QAction("拡大", viewer, shortcut="+")
    viewer.zoom_in_action.setShortcutContext(Qt.WindowShortcut)
    viewer.zoom_in_action.triggered.connect(lambda: viewer.set_zoom(min(viewer.scale * 2, MAX_ZOOM_SCALE)))
    viewer.addAction(viewer.zoom_in_action)

    viewer.zoom_out_action = QAction("縮小", viewer, shortcut="-")
    viewer.zoom_out_action.setShortcutContext(Qt.WindowShortcut)
    viewer.zoom_out_action.triggered.connect(lambda: viewer.set_zoom(max(viewer.scale / 2, MIN_ZOOM_SCALE)))
    viewer.addAction(viewer.zoom_out_action)

    # Image menu (must be created after navigation actions are defined)
    viewer.img_menu = menubar.addMenu("画像")
    viewer.update_image_list_menu()

    # View menu
    view_menu = menubar.addMenu("表示")
    view_menu.addAction(viewer.show_display_settings_action)
    view_menu.addSeparator()
    view_menu.addAction(viewer.zoom_in_action)
    view_menu.addAction(viewer.zoom_out_action)

    # Analysis menu
    analysis = menubar.addMenu("解析")
    analysis.addAction(viewer.show_analysis_action)
    analysis.addSeparator()
    analysis.addAction(viewer.show_features_action)
    analysis.addSeparator()
    analysis.addAction(QAction("差分画像表示", viewer, triggered=lambda: viewer.show_diff_dialog()))
    analysis.addAction(QAction("タイリング比較", viewer, triggered=lambda: viewer.show_tiling_comparison_dialog()))

    # Help menu
    help_menu = menubar.addMenu("ヘルプ")
    help_menu.addAction(QAction("その他キーボードショートカット", viewer, triggered=viewer.help_dialog.show))

    # Add global application-level shortcuts
    _create_global_shortcuts(viewer)


def _create_global_shortcuts(viewer):
    """Create application-level keyboard shortcuts.

    These shortcuts work even when dialogs are focused.

    Args:
        viewer: ImageViewer instance
    """
    # Reset brightness shortcut
    viewer.reset_brightness_action = QAction(viewer)
    viewer.reset_brightness_action.setShortcut("Ctrl+R")
    viewer.reset_brightness_action.setShortcutContext(Qt.WindowShortcut)
    viewer.reset_brightness_action.triggered.connect(viewer.reset_brightness_settings)
    viewer.addAction(viewer.reset_brightness_action)

    # Gain adjustment shortcuts
    viewer.left_gain_adjust_action = QAction(viewer)
    viewer.left_gain_adjust_action.setShortcut("<")
    viewer.left_gain_adjust_action.setShortcutContext(Qt.WindowShortcut)
    viewer.left_gain_adjust_action.triggered.connect(lambda: viewer.adjust_gain_step(-1))
    viewer.addAction(viewer.left_gain_adjust_action)

    viewer.right_gain_adjust_action = QAction(viewer)
    viewer.right_gain_adjust_action.setShortcut(">")
    viewer.right_gain_adjust_action.setShortcutContext(Qt.WindowShortcut)
    viewer.right_gain_adjust_action.triggered.connect(lambda: viewer.adjust_gain_step(1))
    viewer.addAction(viewer.right_gain_adjust_action)

    # Fit zoom toggle shortcut
    viewer.fit_toggle_action = QAction(viewer)
    viewer.fit_toggle_action.setShortcut("f")
    viewer.fit_toggle_action.setShortcutContext(Qt.WindowShortcut)
    viewer.fit_toggle_action.triggered.connect(viewer.toggle_fit_zoom)
    viewer.addAction(viewer.fit_toggle_action)

    # Note: Navigation, zoom, and dialog shortcuts (n, b, +, -, D, A, T) are now
    # defined in create_menus() to avoid duplication and ensure shortcuts are visible in menus
