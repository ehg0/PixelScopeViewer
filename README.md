# pyside6_imageViewer (refactored)

Small image viewer and light analysis tools built with PySide6.

Project structure (high level)

- pyside_image_viewer/
	- main.py           # entrypoint (application startup)
	- utils.py          # compatibility wrapper re-exporting IO helpers
	- ui/               # UI components
		- viewer.py       # ImageViewer main window (recommended import)
		- widgets.py      # ImageLabel and other widgets
		- dialogs.py      # small dialogs (help)
	- io/               # image I/O helpers
		- image_io.py     # numpy <-> QImage, Pillow loading, file checks

Quick start (Windows PowerShell):

```powershell
python -m pip install -r requirements.txt
python .\app_2.py
```

Recommended imports

Prefer the `ui` subpackage in new code:

```python
from pyside_image_viewer.ui.viewer import ImageViewer
# or
from pyside_image_viewer.ui import ImageViewer
```

For IO helpers use the `io` subpackage (top-level `utils.py` still re-exports them):

```python
from pyside_image_viewer.io import pil_to_numpy, numpy_to_qimage
```

Notes

- Backwards-compatible thin wrappers remain at the package root (e.g. `pyside_image_viewer.viewer`) so existing imports should continue to work.
- If you want, we can further add an `analysis` subpackage (histograms, profiles, diff) and move analysis code there.
