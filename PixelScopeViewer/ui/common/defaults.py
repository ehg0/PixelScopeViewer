"""UI の初期値（window サイズ・dialog の初期設定）。"""

# --- window サイズ (width, height) ---
MAIN_WINDOW_SIZE = (1000, 700)
ANALYSIS_DIALOG_SIZE = (900, 600)
DISPLAY_DIALOG_SIZE = (500, 450)
DIFF_DIALOG_SIZE = (400, 120)
FEATURES_DIALOG_SIZE = (900, 600)
FEATURES_COLUMN_DIALOG_SIZE = (300, 400)
HELP_DIALOG_SIZE = (640, 520)
TILING_DIALOG_SIZE = (1200, 800)
TILING_BRIGHTNESS_DIALOG_SIZE = (400, 500)
TILING_HELP_DIALOG_SIZE = (760, 640)
TILE_SELECTION_DIALOG_SIZE = (500, 600)

# --- 解析 dialog ---
PROFILE_ORIENTATION = "h"  # "h", "v"
PROFILE_X_MODE = "relative"  # "relative", "absolute"
PROFILE_METHOD = "mean"  # "mean", "std", "max", "min", "p2p", "median"
HIST_MODE = "Histogram"  # "Histogram", "ECDF"
HIST_YSCALE = "linear"
HIST_CHART_KIND = "Line"  # "Line", "Bar"
HIST_BIN_STEP = 1.0
HIST_BAR_ALPHA = 120
# 画像を切り替えても保持する plot 設定の初期値
PLOT_SETTINGS = {
    "hist": {"grid": True, "log": False, "auto_range": True},
    "prof": {"grid": True, "auto_range": True},
}
# channel の checkbox の最大数
MAX_CHANNEL_CHECKBOXES = 8

# --- 複数画像比較 ---
# 選択できる grid サイズ (rows, cols) と初期値
TILE_GRID_SIZES = ((1, 2), (1, 3), (1, 4), (2, 1), (2, 2), (2, 3), (2, 4), (3, 2), (3, 3))
TILE_GRID_SIZE = (3, 3)
