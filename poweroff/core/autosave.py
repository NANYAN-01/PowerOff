"""关机前自动保存：枚举可见顶层窗口，对文档类应用逐个激活并发送 Ctrl+S。

策略（尽力而为）：
- 只处理白名单进程（Office/WPS/记事本/编辑器等），避免对无关程序乱发按键；
- 逐个 SetForegroundWindow 激活成功后发送 Ctrl+S，失败则跳过该窗口；
- 受总时长预算约束，保证不显著推迟关机。
"""
from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from typing import List

# 文档类进程白名单（不含 .exe 后缀，统一小写比较）
DOCUMENT_PROCESSES = frozenset({
    # Microsoft Office
    "winword", "excel", "powerpnt", "onenote", "msaccess", "visio",
    # WPS 系列
    "wps", "wpp", "et", "wpsoffice", "wpspdf", "wpscloudsvr",
    # 文本/代码编辑器
    "notepad", "wordpad", "write", "notepad++", "sublime_text",
    "code", "codium", "atom", "idea64", "pycharm64", "webstorm64",
    "devenv", "vim", "gvim",
    # 设计/阅读
    "acad", "coreldrw", "photoshop", "sumatrapdf", "foxitreader",
})

MAX_WINDOWS = 8
WINDOW_DELAY = 0.4       # 每个窗口发送后的停留时间（给应用留保存时间）
TOTAL_BUDGET = 15.0      # 总时长预算（秒）
FOCUS_WAIT = 0.3         # 等待获得前台焦点的上限

VK_CONTROL = 0x11
VK_S = 0x53
KEYEVENTF_KEYUP = 0x0002
GW_OWNER = 4

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_user32.EnumWindows.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
_user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
_user32.IsWindowVisible.restype = ctypes.c_bool
_user32.GetWindow.argtypes = [ctypes.c_void_p, ctypes.c_uint]
_user32.GetWindow.restype = ctypes.c_void_p
_user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
_user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
_user32.GetWindowThreadProcessId.argtypes = [ctypes.c_void_p,
                                             ctypes.POINTER(wintypes.DWORD)]
_user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
_user32.GetForegroundWindow.restype = ctypes.c_void_p
_user32.IsIconic.argtypes = [ctypes.c_void_p]
_user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
_user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, ctypes.c_bool]
_user32.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD,
                                ctypes.c_ulong]
_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.GetCurrentThreadId.restype = wintypes.DWORD
try:
    _kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD)]
    _kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    _HAS_QUERY_NAME = True
except AttributeError:
    _HAS_QUERY_NAME = False

PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SW_RESTORE = 9


@dataclass
class SaveReport:
    scanned: int = 0
    saved: List[str] = field(default_factory=list)      # 成功保存的窗口标题
    failed: List[str] = field(default_factory=list)     # 激活/发送失败的标题
    expired: bool = False                               # 预算耗尽提前结束


def iter_visible_windows() -> List[int]:
    """枚举可见的顶层窗口句柄（带标题、非 owned）。"""
    hwnds: List[int] = []

    def _callback(handle, _lparam):
        handle = int(handle)
        if not _user32.IsWindowVisible(handle):
            return True
        if _user32.GetWindow(handle, GW_OWNER):
            return True
        if _user32.GetWindowTextLengthW(handle) == 0:
            return True
        hwnds.append(handle)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    _user32.EnumWindows(WNDENUMPROC(_callback), None)
    return hwnds


def process_name(hwnd: int) -> str:
    """窗口所属进程的可执行文件名（小写、不含 .exe），取不到返回空串。"""
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if not pid.value:
        return ""
    handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION,
                                   False, pid.value)
    if not handle:
        return ""
    try:
        if not _HAS_QUERY_NAME:
            return ""
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if not _kernel32.QueryFullProcessImageNameW(handle, 0, buffer,
                                                    ctypes.byref(size)):
            return ""
        return os.path.splitext(os.path.basename(buffer.value))[0].lower()
    finally:
        _kernel32.CloseHandle(handle)


def activate(hwnd: int) -> bool:
    """把窗口切换到前台（处理最小化与前台锁定），成功返回 True。"""
    if _user32.IsIconic(hwnd):
        _user32.ShowWindow(hwnd, SW_RESTORE)
    if _user32.GetForegroundWindow() == hwnd:
        return True
    fg = _user32.GetForegroundWindow()
    cur = _kernel32.GetCurrentThreadId()
    attached = False
    if fg:
        fg_thread = _user32.GetWindowThreadProcessId(fg, None)
        attached = bool(fg_thread) and bool(_user32.AttachThreadInput(
            cur, fg_thread, True))
    try:
        _user32.SetForegroundWindow(hwnd)
        deadline = time.time() + FOCUS_WAIT
        while time.time() < deadline:
            if _user32.GetForegroundWindow() == hwnd:
                return True
            time.sleep(0.03)
    finally:
        if attached:
            _user32.AttachThreadInput(cur, fg, False)
    return _user32.GetForegroundWindow() == hwnd


def send_ctrl_s() -> None:
    """向当前前台窗口发送 Ctrl+S。"""
    _user32.keybd_event(VK_CONTROL, 0, 0, 0)
    time.sleep(0.02)
    _user32.keybd_event(VK_S, 0, 0, 0)
    time.sleep(0.02)
    _user32.keybd_event(VK_S, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(0.02)
    _user32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)


def save_all_documents(max_windows: int = MAX_WINDOWS,
                       budget: float = TOTAL_BUDGET) -> SaveReport:
    """对白名单文档窗口逐个发送 Ctrl+S，返回保存报告。"""
    report = SaveReport()
    started = time.time()
    for hwnd in iter_visible_windows():
        if len(report.saved) + len(report.failed) >= max_windows:
            break
        if time.time() - started > budget:
            report.expired = True
            break
        name = process_name(hwnd)
        if name not in DOCUMENT_PROCESSES:
            continue
        report.scanned += 1
        title = ""
        length = _user32.GetWindowTextLengthW(hwnd)
        if length:
            buffer = ctypes.create_unicode_buffer(length + 1)
            _user32.GetWindowTextW(hwnd, buffer, length + 1)
            title = buffer.value or name
        if not activate(hwnd):
            report.failed.append(title or name)
            continue
        send_ctrl_s()
        report.saved.append(title or name)
        time.sleep(WINDOW_DELAY)
    return report
