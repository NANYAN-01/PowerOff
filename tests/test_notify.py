"""core.notify 单元测试：成功透传与失败静默。"""
from poweroff.core import notify


def test_toast_success_passes_arguments(monkeypatch):
    calls = {}

    def fake_show(app_id, title, msg, sound):
        calls.update(app_id=app_id, title=title, msg=msg, sound=sound)

    monkeypatch.setattr(notify, "_show", fake_show)
    assert notify.toast("标题", "内容") is True
    assert calls == {"app_id": notify.APP_ID, "title": "标题",
                     "msg": "内容", "sound": True}


def test_toast_sound_flag(monkeypatch):
    rec = {}
    monkeypatch.setattr(notify, "_show",
                        lambda a, t, m, s: rec.update(sound=s))
    notify.toast("t", "m", sound=False)
    assert rec["sound"] is False


def test_toast_swallows_errors(monkeypatch):
    def boom(*_args, **_kwargs):
        raise RuntimeError("powershell unavailable")

    monkeypatch.setattr(notify, "_show", boom)
    assert notify.toast("t", "m") is False
