"""开机自启：写入 HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run。"""
from __future__ import annotations

import os
import sys

from PyQt5.QtCore import QSettings

AUTOSTART_KEY = "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run"
AUTOSTART_NAME = "PowerOff"


def _settings() -> QSettings:
    return QSettings(AUTOSTART_KEY, QSettings.NativeFormat)


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _command() -> str:
    if getattr(sys, "frozen", False):
        return '"{}"'.format(sys.executable)
    return '"{}" "{}"'.format(sys.executable, os.path.join(_project_root(), "main.py"))


def is_enabled() -> bool:
    return AUTOSTART_NAME in _settings().allKeys()


def set_enabled(enabled: bool) -> None:
    settings = _settings()
    if enabled:
        settings.setValue(AUTOSTART_NAME, _command())
    else:
        settings.remove(AUTOSTART_NAME)
