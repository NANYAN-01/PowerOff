import time
from unittest.mock import MagicMock, patch

from poweroff.core.power import (Backend, PowerAction,
                                 RC_NOTHING_TO_CANCEL)
from poweroff.core import state as state_module
from poweroff.ui import main_window as mw


def make_widget(qapp, prefs, state_file):
    return mw.PowerOffWidget()


def test_action_radios_are_exclusive(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    for radio, expected in ((widget.sleepRadio, PowerAction.SLEEP),
                            (widget.hibernateRadio, PowerAction.HIBERNATE),
                            (widget.lockRadio, PowerAction.LOCK),
                            (widget.logRadio, PowerAction.LOGOFF),
                            (widget.rebootRadio, PowerAction.REBOOT),
                            (widget.shutRadio, PowerAction.SHUTDOWN)):
        radio.setChecked(True)
        checked = [r for r in widget.actionGroup.buttons() if r.isChecked()]
        assert checked == [radio]
        assert widget.current_action() is expected


def test_force_only_enabled_for_shutdown_reboot(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    widget.shutRadio.setChecked(True)
    assert widget.forceChk.isEnabled()
    widget.rebootRadio.setChecked(True)
    assert widget.forceChk.isEnabled()
    for radio in (widget.logRadio, widget.sleepRadio,
                  widget.hibernateRadio, widget.lockRadio):
        radio.setChecked(True)
        assert not widget.forceChk.isEnabled()


def test_apply_preset_switches_to_countdown(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    widget.apply_preset(45)
    assert widget.countRadio.isChecked()
    assert (widget.hourSpin.value(), widget.minSpin.value(), widget.secSpin.value()) == (0, 45, 0)
    widget.apply_preset(90)
    assert (widget.hourSpin.value(), widget.minSpin.value(), widget.secSpin.value()) == (1, 30, 0)


def test_prefs_roundtrip(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    widget.countRadio.setChecked(True)
    widget.lockRadio.setChecked(True)
    widget.forceChk.setChecked(False)
    widget.topChk.setChecked(True)
    widget.save_prefs()

    restored = make_widget(qapp, prefs, state_file)
    assert restored.countRadio.isChecked()
    assert restored.current_action() is PowerAction.LOCK
    assert not restored.forceChk.isChecked()
    assert restored.topChk.isChecked()
    assert bool(restored.windowFlags() & mw.Qt.WindowStaysOnTopHint)


def test_handle_ok_logoff_uses_local_backend(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    with patch.object(mw, "QMessageBox") as box, \
            patch.object(mw, "execute_immediate") as immediate:
        immediate.return_value = MagicMock(ok=True)
        widget.logRadio.setChecked(True)
        widget.countRadio.setChecked(True)
        widget.minSpin.setValue(10)
        widget.handle_ok()

    assert widget.plan is not None
    assert widget.plan["backend"] is Backend.LOCAL
    assert widget.plan["action"] is PowerAction.LOGOFF
    assert immediate.call_count == 0  # 尚未到点
    saved = state_module.load_state()
    assert saved is not None and saved.action == "logoff" and saved.backend == "local"


def test_handle_ok_forced_shutdown_uses_system_backend(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    with patch.object(mw, "QMessageBox"), \
            patch.object(mw, "schedule_system") as schedule:
        schedule.return_value = MagicMock(ok=True)
        widget.shutRadio.setChecked(True)
        widget.forceChk.setChecked(True)
        widget.countRadio.setChecked(True)
        widget.minSpin.setValue(10)
        widget.handle_ok()

    assert widget.plan["backend"] is Backend.SYSTEM
    args = schedule.call_args[0]
    assert args[0] is PowerAction.SHUTDOWN and args[1] == 600 and args[2] is True


def test_handle_ok_reports_schedule_failure(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    with patch.object(mw, "QMessageBox") as box, \
            patch.object(mw, "schedule_system") as schedule:
        schedule.return_value = MagicMock(ok=False, hint="已存在其他关机计划")
        widget.countRadio.setChecked(True)
        widget.minSpin.setValue(5)
        widget.handle_ok()

    assert widget.plan is None
    assert box.critical.called
    assert state_module.load_state() is None


def test_handle_ok_rejects_past_target(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    with patch.object(mw, "QMessageBox") as box:
        widget.specRadio.setChecked(True)
        widget.handle_ok()
    assert box.warning.called and widget.plan is None


def test_fire_local_plan_clears_state(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    widget.plan = {"action": PowerAction.LOGOFF, "force": False,
                   "backend": Backend.LOCAL,
                   "deadline": time.time() - 1, "created": time.time()}
    widget.persist_plan()

    with patch.object(mw, "QMessageBox"), \
            patch.object(mw, "execute_immediate") as immediate:
        immediate.return_value = MagicMock(ok=True)
        widget.updateTime()

    assert immediate.call_args[0] == (PowerAction.LOGOFF, False)
    assert widget.plan is None
    assert state_module.load_state() is None


def test_system_plan_display_clears_after_deadline(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    widget.plan = {"action": PowerAction.SHUTDOWN, "force": True,
                   "backend": Backend.SYSTEM,
                   "deadline": time.time() - 1, "created": time.time()}
    widget.updateTime()
    assert widget.plan is None
    assert state_module.load_state() is None


def test_cancel_clears_plan_on_success(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    widget.plan = {"action": PowerAction.SHUTDOWN, "force": True,
                   "backend": Backend.SYSTEM,
                   "deadline": time.time() + 600, "created": time.time()}
    widget.persist_plan()
    with patch.object(mw, "QMessageBox"), patch.object(mw, "cancel") as cancel_cmd:
        cancel_cmd.return_value = MagicMock(ok=True, returncode=0, hint="")
        widget.cancel_shutdown()
    assert widget.plan is None and state_module.load_state() is None


def test_cancel_keeps_plan_when_cancel_fails(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    widget.plan = {"action": PowerAction.SHUTDOWN, "force": True,
                   "backend": Backend.SYSTEM,
                   "deadline": time.time() + 600, "created": time.time()}
    with patch.object(mw, "QMessageBox") as box, patch.object(mw, "cancel") as cancel_cmd:
        cancel_cmd.return_value = MagicMock(ok=False, returncode=1, hint="拒绝访问")
        widget.cancel_shutdown()
    assert widget.plan is not None
    assert box.critical.called


def test_cancel_clears_plan_when_nothing_to_cancel(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    widget.plan = {"action": PowerAction.SHUTDOWN, "force": True,
                   "backend": Backend.SYSTEM,
                   "deadline": time.time() + 600, "created": time.time()}
    with patch.object(mw, "QMessageBox"), patch.object(mw, "cancel") as cancel_cmd:
        cancel_cmd.return_value = MagicMock(ok=False, returncode=RC_NOTHING_TO_CANCEL, hint="")
        widget.cancel_shutdown()
    assert widget.plan is None


def test_restore_valid_future_plan(qapp, prefs, state_file):
    state_module.save_state(state_module.PlanState(
        action="reboot", force=True, backend="local",
        deadline=time.time() + 300, created=time.time()))
    widget = make_widget(qapp, prefs, state_file)
    assert widget.plan is not None
    assert widget.plan["action"] is PowerAction.REBOOT
    assert widget.plan["backend"] is Backend.LOCAL


def test_restore_drops_expired_plan(qapp, prefs, state_file):
    state_module.save_state(state_module.PlanState(
        action="shutdown", force=True, backend="system",
        deadline=time.time() - 5, created=time.time()))
    widget = make_widget(qapp, prefs, state_file)
    assert widget.plan is None
    assert state_module.load_state() is None


def test_restore_drops_unknown_action(qapp, prefs, state_file):
    state_module.save_state(state_module.PlanState(
        action="explode", force=True, backend="system",
        deadline=time.time() + 300, created=time.time()))
    widget = make_widget(qapp, prefs, state_file)
    assert widget.plan is None
    assert state_module.load_state() is None


def test_level_thresholds(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    widget._blink_on = True
    assert widget.level_for(1801) == "green"
    assert widget.level_for(1800) == "yellow"
    assert widget.level_for(601) == "yellow"
    assert widget.level_for(600) == "orange"
    assert widget.level_for(61) == "orange"
    assert widget.level_for(60) == "red"
    widget._blink_on = False
    assert widget.level_for(30) == "redDark"


def test_status_label_shows_remaining(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    widget.plan = {"action": PowerAction.SHUTDOWN, "force": True,
                   "backend": Backend.SYSTEM,
                   "deadline": time.time() + 3725, "created": time.time()}
    widget._notified = True
    widget.updateTime()
    text = widget.timeLabel.text()
    assert "剩余" in text and "关机" in text and "系统" in text
    assert "01:02:05" in text
    assert widget.timeLabel.property("level") == "green"


def test_immediate_failure_shows_error(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    with patch.object(mw, "QMessageBox") as box, \
            patch.object(mw, "execute_immediate") as immediate:
        box.question.return_value = box.Yes
        immediate.return_value = MagicMock(ok=False, hint="命令失败")
        widget.handle_shutdown_now()
    assert box.critical.called


def test_quit_declined_keeps_local_plan(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    widget.plan = {"action": PowerAction.LOGOFF, "force": False,
                   "backend": Backend.LOCAL,
                   "deadline": time.time() + 100, "created": time.time()}
    with patch.object(mw, "QMessageBox") as box, \
            patch.object(mw.QApplication, "quit") as quit_app:
        box.question.return_value = box.No
        widget.quit_app()
    assert not quit_app.called
    assert widget.plan is not None


def test_quit_confirmed_clears_local_plan(qapp, prefs, state_file):
    widget = make_widget(qapp, prefs, state_file)
    widget.plan = {"action": PowerAction.LOGOFF, "force": False,
                   "backend": Backend.LOCAL,
                   "deadline": time.time() + 100, "created": time.time()}
    widget.persist_plan()
    with patch.object(mw, "QMessageBox") as box, \
            patch.object(mw.QApplication, "quit") as quit_app:
        box.question.return_value = box.Yes
        widget.quit_app()
    assert quit_app.called
    assert widget.plan is None
    assert state_module.load_state() is None
