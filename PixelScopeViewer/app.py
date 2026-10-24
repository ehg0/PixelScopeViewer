"""アプリケーションのエントリポイント。"""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from .ui.viewer import ImageViewer

RESTART_EXIT_CODE = 1001


def main(argv=None):
    """画像ビューアを起動する。

    Args:
        argv: コマンドライン引数。None の場合は sys.argv を使う。

    Returns:
        QApplication.exec() の終了コード。
    """
    if argv is None:
        argv = sys.argv

    # QApplication 生成前に custom loader を登録する
    try:
        project_root = Path(__file__).parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))

        from custom_loaders import load_custom_loaders

        load_custom_loaders()
    except Exception as e:
        print(f"Note: Custom loaders not loaded: {e}")

    app = QApplication(argv)

    # Windows の taskbar で正しく表示されるよう ICO を使う
    icon_ico = Path(__file__).parent / "resources" / "app_icon.ico"
    app.setWindowIcon(QIcon(str(icon_ico)))

    # Windows: taskbar に独自 icon を出すため AppUserModelID を設定する
    try:
        import ctypes

        myappid = "com.pixelscopeviewer.app.0.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass  # Windows 以外、または設定失敗

    w = ImageViewer()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
