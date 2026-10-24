"""Dialogs package."""

from .analysis import AnalysisDialog
from .diff_dialog import DiffDialog
from .display import BrightnessDialog
from .features import FeaturesDialog
from .help_dialog import HelpDialog

__all__ = ["HelpDialog", "DiffDialog", "BrightnessDialog", "AnalysisDialog", "FeaturesDialog"]
