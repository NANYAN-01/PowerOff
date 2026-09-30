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
