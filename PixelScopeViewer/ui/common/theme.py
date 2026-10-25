"""UI の色と、色を含む stylesheet。

色は Qt 非依存の hex 文字列（QColor・pyqtgraph・stylesheet のいずれにも渡せる）で定義する。
RGB tuple が必要な palette のみ tuple で定義する。
"""

# --- channel の既定色 ---
CHANNEL_COLOR_1CH = "#ffffff"
# 2ch（optical flow）は flow_x を赤、flow_y を緑にする（HSV の hue）
CHANNEL_HUES_2CH = (0, 120)
CHANNEL_COLORS_3CH = ("#ff0000", "#00ff00", "#0000ff")
# 4ch は RGBIR を想定
CHANNEL_COLORS_4CH = (*CHANNEL_COLORS_3CH, "#7f7f7f")
# 5ch 以上は hue を均等に割り当てる。見やすさのため saturation は控えめにする
CHANNEL_SATURATION_MANY = 200

# --- plot（histogram・profile）---
PLOT_BACKGROUND = "#ffffff"
PLOT_AXIS_COLOR = "#7f8c8d"
PLOT_TEXT_COLOR = "#2c3e50"
# 描画対象がないときの title と、色を決められない curve
PLOT_MUTED_COLOR = "#7f8c8d"
# Intensity（1ch）と grayscale の channel は黒で描画する
PLOT_INTENSITY_COLOR = "#000000"
# channel の色が渡されないときの curve の色
PLOT_FALLBACK_CHANNEL_COLORS = ("#ff0000", "#00c800", "#0066ff", "#7f7f7f")
PLOT_FALLBACK_COLOR = "#7f7f7f"

# 複数画像比較の重ね描きの色（Tableau 20）。灰色系はグラフ上では黒で描く
OVERLAY_PALETTE: tuple[str, ...] = (
    "#1f77b4",
    "#aec7e8",
    "#ff7f0e",
    "#ffbb78",
    "#2ca02c",
    "#98df8a",
    "#d62728",
    "#ff9896",
    "#9467bd",
    "#c5b0d5",
    "#8c564b",
    "#c49c94",
    "#e377c2",
    "#f7b6d2",
    "#7f7f7f",
    "#c7c7c7",
    "#bcbd22",
    "#dbdb8d",
    "#17becf",
    "#9edae5",
)

# --- 画像上の描画 ---
ROI_COLOR = "#33ff66"
ROI_INACTIVE_COLOR = "#aaaaaa"
# ROI 一覧の名前（R1 など）の背景
ROI_LABEL_BACKGROUND = "#ffffff"
NAVIGATOR_VIEW_RECT_COLOR = "#ff4444"
# colorbar の両端の label（RGB）
COLORBAR_LABEL_RGB = (255, 255, 255)
# 画像メニューで表示中の画像に付ける印
CURRENT_IMAGE_MARKER_COLOR = "#000000"

# --- table・label ---
# 表示中の画像の行、metadata の値が異なる cell
HIGHLIGHT_BACKGROUND = "#ffffc8"
TEXT_COLOR = "#000000"
# 読み込まれていない画像の行、補足の label
TEXT_MUTED_COLOR = "#808080"
TEXT_HINT_COLOR = "#888888"
COLOR_BUTTON_BORDER = "#999999"
GROUP_BOX_BORDER = "#cccccc"
DIALOG_BACKGROUND = "#fafafa"

# --- tile（複数画像比較）---
TILE_ACTIVE_BORDER = "#0078d4"
TILE_INACTIVE_BORDER = "#cccccc"
TILE_STATUS_BACKGROUND = "rgba(50, 50, 50, 200)"
TILE_STATUS_TEXT = "#ffffff"

# --- slider ---
SLIDER_GROOVE = "#dddddd"
SLIDER_HANDLE = "#666666"
SLIDER_HANDLE_HOVER = "#444444"


# --- stylesheet ---
GROUP_BOX_STYLESHEET = f"""
    QGroupBox {{
        font-weight: bold;
        border: 2px solid {GROUP_BOX_BORDER};
        border-radius: 5px;
        margin: 3px 0px;
        padding-top: 10px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px 0 5px;
    }}
"""

SLIDER_STYLESHEET = f"""
    QSlider::groove:horizontal {{ background: {SLIDER_GROOVE}; height: 6px; border-radius: 3px; }}
    QSlider::handle:horizontal {{ background: {SLIDER_HANDLE}; width: 16px; margin: -5px 0; border-radius: 8px; }}
    QSlider::handle:horizontal:hover {{ background: {SLIDER_HANDLE_HOVER}; }}
"""

TILE_STATUS_STYLESHEET = f"QWidget {{ background-color: {TILE_STATUS_BACKGROUND}; }}"
TILE_FILENAME_STYLESHEET = (
    f"QLabel {{ color: {TILE_STATUS_TEXT}; font-size: 11pt; font-weight: bold;"
    " background-color: transparent; border: none; }"
)
TILE_PIXEL_VALUE_STYLESHEET = (
    f"QLabel {{ color: {TILE_STATUS_TEXT}; font-size: 11pt; background-color: transparent; border: none; }}"
)
TILE_ACTIVE_FRAME_STYLESHEET = (
    f"QFrame {{ border: 2px solid {TILE_ACTIVE_BORDER}; background-color: palette(window); }}"
)
TILE_INACTIVE_FRAME_STYLESHEET = (
    f"QFrame {{ border: 2px solid {TILE_INACTIVE_BORDER}; background-color: palette(window); }}"
)
