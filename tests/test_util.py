import os

from poweroff.core.util import format_duration, resource_path


def test_format_duration_basic():
    assert format_duration(45) == "00:00:45"
    assert format_duration(90) == "00:01:30"
    assert format_duration(3661) == "01:01:01"


def test_format_duration_with_days():
    assert format_duration(90061) == "1天 01:01:01"


def test_format_duration_clamps_negative():
    assert format_duration(-10) == "00:00:00"


def test_resource_path_resolves_icon():
    path = resource_path("app_icon.ico")
    assert os.path.basename(path) == "app_icon.ico"
    assert os.path.exists(path)
