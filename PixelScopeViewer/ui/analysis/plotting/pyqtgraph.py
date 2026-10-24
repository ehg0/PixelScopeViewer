"""pyqtgraph の ViewBox 状態の保存・復元と、grid/log 設定の同期。"""

from __future__ import annotations

import contextlib


def save_viewbox_state(vb) -> dict | None:
    """ViewBox の状態を返す。取得できない場合は None。"""
    try:
        return vb.getState(copy=True)
    except Exception:
        return None


def apply_plot_settings(widget, which: str, plot_settings: dict[str, dict], saved_full_state: dict | None = None):
    """grid 設定を適用し、saved_full_state があれば ViewBox の状態を復元する。"""
    try:
        s = plot_settings.get(which, {})
        widget.showGrid(x=bool(s.get("grid", True)), y=bool(s.get("grid", True)))
    except Exception:
        pass

    if saved_full_state is not None:
        try:
            vb = widget.getViewBox()
            vb.setState(saved_full_state)
        except Exception:
            pass


def connect_plot_controls(plot_item, which: str, plot_settings: dict[str, dict], on_hist_log_changed=None):
    """PlotItem の grid/log の checkbox の変更を plot_settings に保存するよう接続する。

    which が 'hist' の場合は log X/Y の変更時に on_hist_log_changed を呼ぶ。
    """
    if not hasattr(plot_item, "ctrl"):
        return
    c = plot_item.ctrl
    # 現在の grid 状態を反映する
    try:
        gval = False
        with contextlib.suppress(Exception):
            gval = bool(c.xGridCheck.isChecked() or c.yGridCheck.isChecked())
        plot_settings.setdefault(which, {})["grid"] = gval
    except Exception:
        pass

    try:
        if hasattr(c, "xGridCheck"):
            c.xGridCheck.toggled.connect(lambda checked: _on_grid_toggled(which, plot_settings, checked))
        if hasattr(c, "yGridCheck"):
            c.yGridCheck.toggled.connect(lambda checked: _on_grid_toggled(which, plot_settings, checked))
    except Exception:
        pass

    if which == "hist":
        try:
            if hasattr(c, "logYCheck"):
                with contextlib.suppress(Exception):
                    plot_settings.setdefault("hist", {})["log"] = bool(c.logYCheck.isChecked())
                c.logYCheck.toggled.connect(
                    lambda checked: _on_log_toggled(plot_settings, bool(checked), on_hist_log_changed)
                )
            # Bar は自前で log 変換するため、log X の変更時も再描画する
            if hasattr(c, "logXCheck") and on_hist_log_changed is not None:
                c.logXCheck.toggled.connect(lambda _checked: on_hist_log_changed())
        except Exception:
            pass


def _on_grid_toggled(which: str, plot_settings: dict[str, dict], checked: bool):
    with contextlib.suppress(Exception):
        plot_settings.setdefault(which, {})["grid"] = bool(checked)


def _on_log_toggled(plot_settings: dict[str, dict], checked: bool, on_hist_log_changed=None):
    try:
        plot_settings.setdefault("hist", {})["log"] = bool(checked)
        if on_hist_log_changed is not None:
            on_hist_log_changed()
    except Exception:
        pass
