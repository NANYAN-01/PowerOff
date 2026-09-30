"""重复计划与计划列表的界面流程测试。"""
import time
from unittest.mock import MagicMock, patch

from poweroff.core import planner, state as state_module
from poweroff.core.power import PowerAction
from poweroff.ui import main_window as mw


def make_widget(qapp, prefs, state_file):
    return mw.PowerOffWidget()


def add_plan(widget, mode, time_str="23:00:00", **kwargs):
    widget.repeatCombo.setCurrentText(mode)
    widget.timeEdit.setTime(mw.QTime(*[int(x) for x in time_str.split(":")]))
    if "dates" in kwargs:
        widget.datesList.clear()
        widget.datesList.addItems(kwargs["dates"])
    with patch.object(mw, "QMessageBox"):
        widget.handle_ok()


def test_add_daily_plan_updates_table_and_state(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    add_plan(widget, "每天")
    assert len(widget.plans) == 1
    plan = widget.plans[0]
    assert plan["repeat"] == planner.REPEAT_DAILY
    assert plan["enabled"] is True
    assert plan["next_run"] > time.time()
    assert widget.planTable.rowCount() == 1
    assert state_module.load_plans()[0]["id"] == plan["id"]


def test_workday_plan_defaults_mon_to_fri(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    add_plan(widget, "工作日")
    assert widget.plans[0]["repeat"] == planner.REPEAT_WEEKDAYS
    assert widget.plans[0]["weekdays"] == [0, 1, 2, 3, 4]
    assert planner.describe(widget.plans[0]).startswith("工作日 ")


def test_custom_plan_requires_weekday(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    widget.repeatCombo.setCurrentText("自定义")
    for chk in widget.weekdayChks:
        chk.setChecked(False)
    with patch.object(mw, "QMessageBox") as box:
        widget.handle_ok()
    assert box.warning.called
    assert widget.plans == []
    widget.weekdayChks[5].setChecked(True)
    add_plan(widget, "自定义")
    assert widget.plans[0]["weekdays"] == [5]


def test_dates_plan_requires_date(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    with patch.object(mw, "QMessageBox") as box:
        widget.repeatCombo.setCurrentText("指定日")
        widget.handle_ok()
    assert box.warning.called
    assert widget.plans == []
    add_plan(widget, "指定日", dates=["2099-10-01"])
    assert widget.plans[0]["repeat"] == planner.REPEAT_DATES
    assert widget.plans[0]["dates"] == ["2099-10-01"]


def test_cn_workday_plan_schedules(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    add_plan(widget, "法定工作日")
    plan = widget.plans[0]
    assert plan["repeat"] == planner.REPEAT_CN_WORKDAY
    assert plan["next_run"] > time.time()


def test_due_plan_fires_and_reschedules(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    add_plan(widget, "每天")
    with patch.object(mw, "execute_immediate") as immediate, \
            patch.object(mw, "QMessageBox"):
        immediate.return_value = MagicMock(ok=True)
        widget.plans[0]["next_run"] = time.time() - 3
        widget.tick_plans(time.time())
    assert immediate.called
    assert widget.plans[0]["next_run"] > time.time()
    assert widget.planTable.rowCount() == 1


def test_stale_plan_skips_to_next_run(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    add_plan(widget, "每天")
    with patch.object(mw, "execute_immediate") as immediate:
        widget.plans[0]["next_run"] = time.time() - 600
        widget.tick_plans(time.time())
    assert not immediate.called
    assert widget.plans[0]["next_run"] > time.time()


def test_disabled_plan_does_not_fire(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    add_plan(widget, "每天")
    plan_id = widget.plans[0]["id"]
    widget.toggle_plan_enabled(plan_id, False)
    assert state_module.load_plans()[0]["enabled"] is False
    with patch.object(mw, "execute_immediate") as immediate:
        widget.plans[0]["next_run"] = time.time() - 3
        widget.tick_plans(time.time())
    assert not immediate.called


def test_delete_plan_persists(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    add_plan(widget, "每天")
    plan_id = widget.plans[0]["id"]
    widget.delete_plan(plan_id)
    assert widget.plans == []
    assert widget.planTable.rowCount() == 0
    assert state_module.load_plans() == []


def test_once_mode_uses_system_backend(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    widget.repeatCombo.setCurrentText("不重复")
    widget.dateEdit.setDate(mw.QDate.currentDate().addDays(1))
    widget.timeEdit.setTime(mw.QTime(20, 0, 0))
    with patch.object(mw, "QMessageBox"), \
            patch.object(mw, "schedule_system") as system:
        system.return_value = MagicMock(ok=True)
        widget.handle_ok()
    assert system.called
    assert widget.plan is not None
    assert widget.planTable.rowCount() == 1  # 单次计划也显示在列表


def test_execute_with_autosave_gating(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    with patch.object(mw, "_run_autosave") as save, \
            patch.object(mw, "execute_immediate") as immediate:
        immediate.return_value = MagicMock(ok=True)
        widget.autosaveChk.setChecked(True)
        widget.execute_with_autosave(PowerAction.SHUTDOWN, True)
        assert save.called and immediate.called
        save.reset_mock()
        widget.execute_with_autosave(PowerAction.LOCK, True)
        assert not save.called  # 锁定不丢数据，不发 Ctrl+S
        widget.autosaveChk.setChecked(False)
        widget.execute_with_autosave(PowerAction.SHUTDOWN, True)
        assert not save.called and immediate.call_count == 3


def test_toast_on_add_and_delete(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    with patch.object(mw, "_toast") as toast:
        add_plan(widget, "每天")
        assert toast.called
        title, msg = toast.call_args[0][:2]
        assert title == "计划已添加"
        assert "每天" in msg
        widget.delete_plan(widget.plans[0]["id"])
        assert toast.call_count == 2
        assert toast.call_args[0][0] == "已删除计划"


def test_execute_toast_before_autosave(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    widget.autosaveChk.setChecked(True)
    with patch.object(mw, "_toast") as toast, \
            patch.object(mw, "_run_autosave") as save, \
            patch.object(mw, "execute_immediate") as immediate:
        immediate.return_value = MagicMock(ok=True)
        widget.execute_with_autosave(PowerAction.SHUTDOWN, True)
        assert toast.called and save.called
        assert toast.call_args[0][0] == "即将执行关机"
