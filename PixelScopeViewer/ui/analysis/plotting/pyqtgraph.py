"""pyqtgraph の ViewBox 状態の保存・復元と、grid/log 設定の同期。"""

from __future__ import annotations


def save_viewbox_state(vb) -> dict:
    """ViewBox の状態を返す。"""
    return vb.getState(copy=True)


def apply_plot_settings(widget, which: str, plot_settings: dict[str, dict], saved_full_state: dict | None = None):
    """grid 設定を適用し、saved_full_state があれば ViewBox の状態を復元する。"""
    grid = bool(plot_settings.get(which, {}).get("grid", True))
    widget.showGrid(x=grid, y=grid)
    if saved_full_state is not None:
        widget.getViewBox().setState(saved_full_state)


def connect_plot_controls(plot_item, which: str, plot_settings: dict[str, dict], on_hist_log_changed=None):
    """PlotItem の menu の grid/log の checkbox の変更を plot_settings に保存するよう接続する。

    which が 'hist' の場合は log X/Y の変更時に on_hist_log_changed を呼ぶ。
    """
    c = plot_item.ctrl
    settings = plot_settings.setdefault(which, {})
    # 現在の grid 状態を反映する
    settings["grid"] = bool(c.xGridCheck.isChecked() or c.yGridCheck.isChecked())
    for check in (c.xGridCheck, c.yGridCheck):
        check.toggled.connect(lambda checked: settings.__setitem__("grid", bool(checked)))

    if which == "hist":
        settings["log"] = bool(c.logYCheck.isChecked())

        def on_log_y(checked: bool):
            settings["log"] = bool(checked)
            if on_hist_log_changed is not None:
                on_hist_log_changed()

        c.logYCheck.toggled.connect(on_log_y)
        # Bar は自前で log 変換するため、log X の変更時も再描画する
        if on_hist_log_changed is not None:
            c.logXCheck.toggled.connect(lambda _checked: on_hist_log_changed())
