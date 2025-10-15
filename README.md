# pyside6_imageViewer (refactored)

This repository contains a small PySide6 image viewer. The code has been refactored into a package `pyside_image_viewer` with modules:

- `utils.py` - helper functions (numpy/pillow ↔ QImage, file checks)
- `widgets.py` - custom widgets like `ImageLabel`
- `dialogs.py` - small dialogs (help)
- `viewer.py` - main application window (`ImageViewer`)
- `main.py` - entry point used by `app_2.py`

Quick start (Windows PowerShell):

```powershell
python -m pip install -r requirements.txt
python app_2.py
```

Notes:
- The refactor splits responsibilities to make maintenance easier.
- Small API-breaking changes: if you previously imported classes from `app_2.py`, import from `pyside_image_viewer.viewer` instead.
