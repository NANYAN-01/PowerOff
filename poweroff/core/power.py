"""系统电源命令层：集中封装 shutdown.exe / rundll32 调用与返回码语义。

约定：
- 只负责执行命令并解释返回码，不弹任何窗口（由 UI 层决定如何呈现）。
- 关机/重启的强制倒计时交给系统（shutdown /t），程序退出后仍然生效；
  注销/睡眠/休眠/锁定以及温和关机不支持系统倒计时，由本程序定时后执行立即命令。
"""
from __future__ import annotations

import locale
import subprocess
from dataclasses import dataclass
from enum import Enum
from typing import Sequence

CREATE_NO_WINDOW = 0x08000000
COMMAND_TIMEOUT = 15

RC_OK = 0
RC_ALREADY_SCHEDULED = 1190
RC_NOTHING_TO_CANCEL = 1116
RC_NOT_FOUND = -1
RC_TIMEOUT = -2

MAX_SYSTEM_TIMEOUT = 315360000


class PowerAction(Enum):
    SHUTDOWN = "shutdown"
    REBOOT = "reboot"
    LOGOFF = "logoff"
    SLEEP = "sleep"
    HIBERNATE = "hibernate"
    LOCK = "lock"

    @property
    def label(self) -> str:
        return _ACTION_LABELS[self]


_ACTION_LABELS = {
    PowerAction.SHUTDOWN: "关机",
    PowerAction.REBOOT: "重启",
    PowerAction.LOGOFF: "注销",
    PowerAction.SLEEP: "睡眠",
    PowerAction.HIBERNATE: "休眠",
    PowerAction.LOCK: "锁定",
}


class Backend(Enum):
    """倒计时执行方式。"""

    SYSTEM = "system"  # shutdown /s|/r /t N，程序关掉后仍然生效
    LOCAL = "local"    # 本程序定时，到点执行立即命令，需保持程序运行


def choose_backend(action: PowerAction, force: bool) -> Backend:
    """关机/重启且强制 -> 系统级倒计时；其余一律本地定时。

    说明：Windows 规定 /t > 0 时自动隐含 /f（强制关闭应用），
    因此温和关机无法用 shutdown /t 实现，只能本地定时后执行 /t 0。
    """
    if action in (PowerAction.SHUTDOWN, PowerAction.REBOOT):
        return Backend.SYSTEM if force else Backend.LOCAL
    return Backend.LOCAL


def _decode(data: bytes) -> str:
    if not data:
        return ""
    for encoding in ("utf-8", locale.getpreferredencoding(False), "gbk"):
        if not encoding:
            continue
        try:
            return data.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return data.decode("utf-8", errors="replace")


@dataclass(frozen=True)
class CommandResult:
    args: tuple
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == RC_OK

    @property
    def raw_message(self) -> str:
        return (self.stderr or self.stdout).strip()

    @property
    def hint(self) -> str:
        """面向用户的中文提示，未知返回码退回原始输出。"""
        if self.ok:
            return "命令执行成功"
        if self.returncode == RC_ALREADY_SCHEDULED:
            return "系统已存在其他关机计划（可能来自 Windows 更新或其他程序），请先取消后再试。"
        if self.returncode == RC_NOTHING_TO_CANCEL:
            return "当前没有计划中的关机任务。"
        if self.returncode == RC_NOT_FOUND:
            return "找不到系统命令，请确认系统为 Windows。"
        if self.returncode == RC_TIMEOUT:
            return "系统命令执行超时。"
        return self.raw_message or f"命令失败，退出码 {self.returncode}"


def run_command(args: Sequence[str]) -> CommandResult:
    argv = [str(a) for a in args]
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            timeout=COMMAND_TIMEOUT,
            creationflags=CREATE_NO_WINDOW,
        )
    except FileNotFoundError:
        return CommandResult(tuple(argv), RC_NOT_FOUND, "", "")
    except subprocess.TimeoutExpired:
        return CommandResult(tuple(argv), RC_TIMEOUT, "", "")
    except OSError as exc:
        return CommandResult(tuple(argv), RC_NOT_FOUND, "", str(exc))
    return CommandResult(
        tuple(argv),
        proc.returncode,
        _decode(proc.stdout),
        _decode(proc.stderr),
    )


def schedule_system(action: PowerAction, seconds: int, force: bool = True) -> CommandResult:
    """系统级倒计时排程（仅关机/重启）。/t > 0 时 Windows 自动隐含 /f。"""
    if action not in (PowerAction.SHUTDOWN, PowerAction.REBOOT):
        raise ValueError(f"{action.label} 不支持系统级倒计时")
    seconds = int(seconds)
    if seconds <= 0:
        raise ValueError("倒计时必须大于 0 秒")
    if seconds > MAX_SYSTEM_TIMEOUT:
        raise ValueError("倒计时超出 Windows 允许的上限（10 年）")
    flag = "/s" if action is PowerAction.SHUTDOWN else "/r"
    args = ["shutdown", flag]
    if force:
        args.append("/f")
    args += ["/t", str(seconds)]
    return run_command(args)


def immediate_command(action: PowerAction, force: bool = False) -> list:
    """本地定时器到点时执行的立即命令。"""
    if action is PowerAction.SHUTDOWN:
        return ["shutdown", "/s"] + (["/f"] if force else []) + ["/t", "0"]
    if action is PowerAction.REBOOT:
        return ["shutdown", "/r"] + (["/f"] if force else []) + ["/t", "0"]
    if action is PowerAction.LOGOFF:
        # /l 独立工作，不能与 /f /t 组合（MS 文档），否则 -t 被忽略导致立即注销
        return ["shutdown", "/l"]
    if action is PowerAction.HIBERNATE:
        return ["shutdown", "/h"]
    if action is PowerAction.SLEEP:
        return ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]
    if action is PowerAction.LOCK:
        return ["rundll32.exe", "user32.dll,LockWorkStation"]
    raise ValueError(f"未知动作：{action}")


def execute_immediate(action: PowerAction, force: bool = False) -> CommandResult:
    return run_command(immediate_command(action, force))


def cancel() -> CommandResult:
    """取消系统级关机计划（shutdown /a）。"""
    return run_command(["shutdown", "/a"])
