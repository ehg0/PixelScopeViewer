"""Plotting helpers for pyqtgraph integration in Analysis dialogs.

This module isolates pyqtgraph-specific interactions: saving/restoring
ViewBox state, connecting control panel toggles, applying grid/log settings,
and showing default context menus. It does not depend on Qt Widgets beyond
what pyqtgraph provides.
"""

from __future__ import annotations


def save_viewbox_state(vb) -> dict | None:
    """Return full ViewBox state if available."""
    try:
        return vb.getState(copy=True)
    except Exception:
        return None


def apply_plot_settings(widget, which: str, plot_settings: dict[str, dict], saved_full_state: dict | None = None):
    """Apply grid settings and restore saved ViewBox state if provided."""
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
    """Connect PlotItem.ctrl toggles to persist grid/log settings.

    For 'hist', also persists LogY and calls on_hist_log_changed when toggled.
    """
    if not hasattr(plot_item, "ctrl"):
        return
    c = plot_item.ctrl
    # initial grid sync
    try:
        gval = False
        try:
            gval = bool(c.xGridCheck.isChecked() or c.yGridCheck.isChecked())
        except Exception:
            pass
        plot_settings.setdefault(which, {})["grid"] = gval
    except Exception:
        pass

    # connect grid toggles
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
                # initial sync
                try:
                    plot_settings.setdefault("hist", {})["log"] = bool(c.logYCheck.isChecked())
                except Exception:
                    pass
                c.logYCheck.toggled.connect(
                    lambda checked: _on_log_toggled(plot_settings, bool(checked), on_hist_log_changed)
                )
        except Exception:
            pass


def _on_grid_toggled(which: str, plot_settings: dict[str, dict], checked: bool):
    try:
        plot_settings.setdefault(which, {})["grid"] = bool(checked)
    except Exception:
        pass


def _on_log_toggled(plot_settings: dict[str, dict], checked: bool, on_hist_log_changed=None):
    try:
        plot_settings.setdefault("hist", {})["log"] = bool(checked)
        if on_hist_log_changed is not None:
            on_hist_log_changed()
    except Exception:
        pass
