"""Application entry point.

This module provides the main() function that initializes the Qt application
and displays the ImageViewer window.

Usage:
    python main.py

    # Or as a module:
    python -m PixelScopeViewer.app

    # Or from Python:
    from PixelScopeViewer import main
    main()
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from .ui.viewer import ImageViewer


def main(argv=None):
    """Run the image viewer application.

    Args:
        argv: Command-line arguments (defaults to sys.argv)

    Returns:
        Exit code from QApplication.exec()
    """
    if argv is None:
        argv = sys.argv
    app = QApplication(argv)

    # Set application icon (prefer ICO for better Windows taskbar support)
    icon_ico = Path(__file__).parent / "resources" / "app_icon.ico"
    app.setWindowIcon(QIcon(str(icon_ico)))

    # Windows: Set AppUserModelID for custom taskbar icon
    try:
        import ctypes

        myappid = "com.pixelscopeviewer.app.0.1.0"
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    except Exception:
        pass  # Not Windows or failed

    w = ImageViewer()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
