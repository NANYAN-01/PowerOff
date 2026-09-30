"""与界面无关的小工具。"""
from __future__ import annotations

import os
import sys


def resource_path(relative_path: str) -> str:
    """获取资源文件的绝对路径，适用于开发环境和打包后的环境。"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def format_duration(total_seconds) -> str:
    total_seconds = max(0, int(total_seconds))
    days, rest = divmod(total_seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, seconds = divmod(rest, 60)
    text = "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)
    return "{}天 {}".format(days, text) if days else text
