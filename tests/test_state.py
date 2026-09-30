import os

from poweroff.core import state


def test_roundtrip(state_file):
    plan = state.PlanState(action="logoff", force=False, backend="local",
                           deadline=1234.5, created=1000.0)
    state.save_state(plan)
    assert state.load_state() == plan
    assert os.path.exists(str(state_file))


def test_load_missing_file(state_file):
    assert state.load_state() is None


def test_load_corrupt_file(state_file):
    state_file.write_text("{not json", encoding="utf-8")
    assert state.load_state() is None


def test_load_missing_keys(state_file):
    state_file.write_text('{"action": "shutdown"}', encoding="utf-8")
    assert state.load_state() is None


def test_load_non_dict(state_file):
    state_file.write_text("[1, 2]", encoding="utf-8")
    assert state.load_state() is None


def test_clear_is_idempotent(state_file):
    state.clear_state()
    state.save_state(state.PlanState(action="shutdown", force=True,
                                     backend="system", deadline=1.0, created=0.0))
    state.clear_state()
    state.clear_state()
    assert state.load_state() is None


def test_plans_roundtrip(state_file):
    plans = [{"id": "abc", "repeat": "daily", "time": "22:00"}]
    state.save_plans(plans)
    assert state.load_plans() == plans
    assert state.load_state() is None


def test_clear_state_keeps_plans(state_file):
    state.save_plans([{"id": "abc", "repeat": "daily"}])
    state.save_state(state.PlanState(action="shutdown", force=True,
                                     backend="system", deadline=1.0, created=0.0))
    state.clear_state()
    assert state.load_state() is None
    assert state.load_plans() == [{"id": "abc", "repeat": "daily"}]


def test_save_plans_keeps_immediate(state_file):
    plan = state.PlanState(action="reboot", force=False, backend="local",
                           deadline=99.0, created=1.0)
    state.save_state(plan)
    state.save_plans([{"id": "x", "repeat": "weekly"}])
    assert state.load_state() == plan
    assert state.load_plans() == [{"id": "x", "repeat": "weekly"}]


def test_old_format_migrates_to_v2(state_file):
    state_file.write_text(
        '{"action": "shutdown", "force": true, "backend": "system",'
        ' "deadline": 123.0, "created": 100.0}', encoding="utf-8")
    loaded = state.load_state()
    assert loaded is not None and loaded.deadline == 123.0
    state.save_plans([{"id": "p", "repeat": "daily"}])
    again = state.load_state()
    assert again is not None and again.deadline == 123.0
    assert state.load_plans() == [{"id": "p", "repeat": "daily"}]


def test_plans_survive_corrupt_file(state_file):
    state_file.write_text("not json", encoding="utf-8")
    assert state.load_plans() == []
    state.save_plans([{"id": "a", "repeat": "daily"}])
    assert state.load_plans() == [{"id": "a", "repeat": "daily"}]
