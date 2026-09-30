"""core.autosave 单元测试：窗口过滤、激活失败与预算限制（全部打桩 Win32）。"""
from unittest.mock import patch

from poweroff.core import autosave


def _drive(hwnds, names, activate_ok=True, **kwargs):
    with patch.object(autosave, "iter_visible_windows", return_value=hwnds), \
            patch.object(autosave, "process_name",
                         side_effect=lambda h: names.get(h, "")), \
            patch.object(autosave, "activate",
                         return_value=activate_ok), \
            patch.object(autosave, "send_ctrl_s") as send, \
            patch.object(autosave, "time") as fake_time:
        fake_time.time.side_effect = [0.0, 0.0, 1.0] + [2.0] * 40
        fake_time.sleep = lambda *_a: None
        report = autosave.save_all_documents(**kwargs)
    return report, send


def test_only_whitelist_processes_are_saved():
    report, send = _drive(
        [1, 2, 3],
        {1: "winword", 2: "chrome", 3: "code"})
    assert report.scanned == 2          # chrome 不计入
    assert len(report.saved) == 2
    assert send.call_count == 2
    assert report.failed == []


def test_activate_failure_is_reported():
    with patch.object(autosave, "iter_visible_windows", return_value=[1]), \
            patch.object(autosave, "process_name", return_value="notepad"), \
            patch.object(autosave, "activate", return_value=False), \
            patch.object(autosave, "send_ctrl_s") as send, \
            patch.object(autosave, "time") as fake_time:
        fake_time.time.side_effect = [0.0, 0.0, 1.0] + [2.0] * 10
        fake_time.sleep = lambda *_a: None
        report = autosave.save_all_documents()
    assert report.saved == []
    assert report.failed == ["notepad"]
    assert not send.called


def test_max_windows_limits_work():
    report, _send = _drive(
        [1, 2, 3],
        {1: "notepad", 2: "winword", 3: "code"},
        max_windows=2)
    assert len(report.saved) == 2


def test_budget_expires():
    report, send = _drive(
        [1],
        {1: "notepad"},
        budget=-1)
    assert report.expired is True
    assert not send.called
