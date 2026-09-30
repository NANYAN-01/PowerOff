"""Windows 右下角 Toast 通知封装（winotify），任何失败都静默降级。

winotify 通过隐藏窗口的 PowerShell 进程弹出原生通知，通知会驻留操作中心；
本模块保证不抛异常，返回是否成功。
"""
from __future__ import annotations

APP_ID = "PowerOff 定时关机工具"


def _show(app_id: str, title: str, msg: str, sound: bool) -> None:
    from winotify import Notification, audio
    note = Notification(app_id=app_id, title=title, msg=msg)
    if sound:
        note.set_audio(audio.Default, loop=False)
    note.show()


def toast(title: str, msg: str, sound: bool = True) -> bool:
    """右下角弹出通知；失败（如环境限制）返回 False，不抛异常。"""
    try:
        _show(APP_ID, title, msg, sound)
        return True
    except Exception:
        return False
