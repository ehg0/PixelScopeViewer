"""Application entry point.

This module provides the main() function that initializes the Qt application
and displays the ImageViewer window.

Usage:
    python main.py

    # Or as a module:
    python -m pyside_image_viewer.app

    # Or from Python:
    from pyside_image_viewer import main
    main()
"""

import sys
from PySide6.QtWidgets import QApplication
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
    w = ImageViewer()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
