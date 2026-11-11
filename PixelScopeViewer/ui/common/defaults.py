"""UI の初期値（window サイズ・dialog の初期設定）。"""

# --- window サイズ (width, height) ---
MAIN_WINDOW_SIZE = (1000, 700)
ANALYSIS_DIALOG_SIZE = (900, 600)
DISPLAY_DIALOG_SIZE = (500, 450)
DIFF_DIALOG_SIZE = (400, 120)
FEATURES_DIALOG_SIZE = (900, 600)
FEATURES_COLUMN_DIALOG_SIZE = (300, 400)
HELP_DIALOG_SIZE = (640, 520)
TILE_REGISTER_DIALOG_SIZE = (1000, 650)

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
# 解析対象の ROI: "active"（編集中ROI）, "overlay", "split"（登録ROI）
ANALYSIS_ROI_MODE = "active"
# Split 表示で全グラフの軸を連動させるか
ANALYSIS_ROI_LINK_AXES = True
# Split 表示で横に並べるグラフの数（1〜6）
ANALYSIS_ROI_SPLIT_COLUMNS = 2
# タイル比較モードの Split の単位: "roi"（ROI ごとに全タイル）, "tile"（タイルごとに全 ROI）
ANALYSIS_ROI_SPLIT_UNIT = "roi"
# channel の checkbox の最大数
MAX_CHANNEL_CHECKBOXES = 8

# --- タイル比較モード ---
# 選択できるグリッド (rows, cols)。1×1 を除く 4×4 までの全組み合わせ
TILE_MAX_GRID = (4, 4)
TILE_GRID_SIZES = tuple(
    (r, c) for r in range(1, TILE_MAX_GRID[0] + 1) for c in range(1, TILE_MAX_GRID[1] + 1) if (r, c) != (1, 1)
)
TILE_GRID_SIZE = (2, 2)
# 表示用の cache（画像ごとの QPixmap）の容量の上限
TILE_DISPLAY_CACHE_MB = 512
# brightness の変更で、active 以外のタイルを描き直すまでの間隔
TILE_BRIGHTNESS_DEBOUNCE_MS = 150
