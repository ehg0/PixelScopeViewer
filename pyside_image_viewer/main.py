import sys
from PySide6.QtWidgets import QApplication
from .ui.viewer import ImageViewer


def main(argv=None):
    if argv is None:
        argv = sys.argv
    app = QApplication(argv)
    w = ImageViewer()
    w.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
