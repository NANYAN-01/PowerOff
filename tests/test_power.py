from unittest.mock import MagicMock, patch

import pytest

from poweroff.core import power


def test_immediate_command_shutdown_force():
    assert power.immediate_command(power.PowerAction.SHUTDOWN, True) == [
        "shutdown", "/s", "/f", "/t", "0"]


def test_immediate_command_gentle_shutdown_has_no_force():
    assert power.immediate_command(power.PowerAction.SHUTDOWN, False) == [
        "shutdown", "/s", "/t", "0"]


def test_logoff_command_is_standalone():
    """Windows 规定 /l 不能与 /t /f 组合，否则 -t 被忽略导致立即注销。"""
    args = power.immediate_command(power.PowerAction.LOGOFF, True)
    assert args == ["shutdown", "/l"]
    assert "/t" not in args and "/f" not in args


def test_other_immediate_commands():
    assert power.immediate_command(power.PowerAction.HIBERNATE) == ["shutdown", "/h"]
    assert power.immediate_command(power.PowerAction.SLEEP) == [
        "rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"]
    assert power.immediate_command(power.PowerAction.LOCK) == [
        "rundll32.exe", "user32.dll,LockWorkStation"]


def test_choose_backend_matrix():
    B = power.Backend
    A = power.PowerAction
    assert power.choose_backend(A.SHUTDOWN, True) is B.SYSTEM
    assert power.choose_backend(A.SHUTDOWN, False) is B.LOCAL
    assert power.choose_backend(A.REBOOT, True) is B.SYSTEM
    assert power.choose_backend(A.REBOOT, False) is B.LOCAL
    for action in (A.LOGOFF, A.SLEEP, A.HIBERNATE, A.LOCK):
        assert power.choose_backend(action, True) is B.LOCAL


def test_schedule_system_builds_argv():
    with patch.object(power, "run_command") as run:
        run.return_value = MagicMock()
        power.schedule_system(power.PowerAction.SHUTDOWN, 600, True)
        assert run.call_args[0][0] == ["shutdown", "/s", "/f", "/t", "600"]
        power.schedule_system(power.PowerAction.REBOOT, 60, False)
        assert run.call_args[0][0] == ["shutdown", "/r", "/t", "60"]


@pytest.mark.parametrize("action", [power.PowerAction.LOGOFF, power.PowerAction.SLEEP,
                                    power.PowerAction.LOCK, power.PowerAction.HIBERNATE])
def test_schedule_system_rejects_local_only_actions(action):
    with pytest.raises(ValueError):
        power.schedule_system(action, 60, True)


@pytest.mark.parametrize("seconds", [0, -5, power.MAX_SYSTEM_TIMEOUT + 1])
def test_schedule_system_rejects_bad_seconds(seconds):
    with pytest.raises(ValueError):
        power.schedule_system(power.PowerAction.SHUTDOWN, seconds, True)


def _fake_proc(returncode, stderr=b""):
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = b""
    proc.stderr = stderr
    return proc


def test_result_codes_and_hints():
    with patch.object(power.subprocess, "run", return_value=_fake_proc(0)):
        assert power.cancel().ok
    with patch.object(power.subprocess, "run",
                      return_value=_fake_proc(1190, "已计划系统关机(1190)\n".encode("gbk"))):
        result = power.cancel()
        assert not result.ok
        assert "已存在其他关机计划" in result.hint
        assert "1190" in result.raw_message
    with patch.object(power.subprocess, "run", return_value=_fake_proc(1116)):
        result = power.cancel()
        assert not result.ok
        assert "没有计划中的关机任务" in result.hint


def test_run_command_missing_binary():
    with patch.object(power.subprocess, "run", side_effect=FileNotFoundError()):
        result = power.run_command(["definitely_not_exists_xyz"])
        assert result.returncode == power.RC_NOT_FOUND
        assert "找不到系统命令" in result.hint


def test_run_command_timeout():
    import subprocess
    with patch.object(power.subprocess, "run",
                      side_effect=subprocess.TimeoutExpired(cmd="x", timeout=1)):
        result = power.run_command(["shutdown", "/a"])
        assert result.returncode == power.RC_TIMEOUT


def test_decode_utf8_input():
    assert power._decode("关机".encode("utf-8")) == "关机"


def test_decode_gbk_console_bytes_do_not_raise():
    """中文 Windows 控制台输出为 GBK，任意区域设置下都不应抛异常。"""
    text = power._decode("已经计划系统关机(1190)".encode("gbk"))
    assert isinstance(text, str) and "1190" in text


def test_decode_empty():
    assert power._decode(b"") == ""


def test_hibernation_enabled_returns_bool_or_none():
    assert power.hibernation_enabled() in (True, False, None)
