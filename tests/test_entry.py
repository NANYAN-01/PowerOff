import main


def test_notify_unknown_server_returns_false(monkeypatch):
    monkeypatch.setattr(main, "SERVER_NAME", "PowerOff.no_such_server")
    assert main.notify_existing_instance() is False
