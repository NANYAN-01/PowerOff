import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt5.QtCore import QSettings
from PyQt5.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from poweroff.core import state as state_module
from poweroff.ui import main_window


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    monkeypatch.setattr(state_module, "STATE_FILE", str(path))
    return path


@pytest.fixture
def prefs(tmp_path, monkeypatch):
    settings = QSettings(str(tmp_path / "prefs.ini"), QSettings.IniFormat)
    monkeypatch.setattr(main_window, "_app_settings", lambda: settings)
    return settings


@pytest.fixture(autouse=True)
def stub_autosave(monkeypatch):
    """UI 测试默认不真发按键，自动保存相关单测直接测 core.autosave。"""
    monkeypatch.setattr(
        main_window, "_run_autosave",
        lambda: main_window.autosave.SaveReport())
