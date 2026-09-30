"""闹钟式计划规则引擎：规则定义、下次执行计算、触发判定与中文描述。

规则类型（repeat）：
- once        单次：指定日期 + 时间，执行一次
- daily       每天：固定时间
- weekdays    自选周几（0=周一 ... 6=周日），含"工作日"（周一~周五）语义
- dates       指定日：一组具体日期，逐个执行
- cn_workday  法定工作日：按中国调休规则（chinese-calendar），含调休补班、
              跳过周末与法定假日；库缺失或无当年数据时退回周一~周五。
"""
from __future__ import annotations

import datetime as dt
import time as _time
import uuid
from typing import Iterable, Optional

REPEAT_ONCE = "once"
REPEAT_DAILY = "daily"
REPEAT_WEEKDAYS = "weekdays"
REPEAT_DATES = "dates"
REPEAT_CN_WORKDAY = "cn_workday"

REPEAT_ORDER = (REPEAT_ONCE, REPEAT_DAILY, REPEAT_WEEKDAYS,
                REPEAT_DATES, REPEAT_CN_WORKDAY)
REPEAT_LABELS = {
    REPEAT_ONCE: "不重复",
    REPEAT_DAILY: "每天",
    REPEAT_WEEKDAYS: "自定义",
    REPEAT_DATES: "指定日",
    REPEAT_CN_WORKDAY: "法定工作日",
}

WEEKDAY_LABELS = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
WEEKDAYS_SET = frozenset({0, 1, 2, 3, 4})

# 错过触发的宽限：唤醒/卡顿后 5 分钟内补执行，更早的跳到下一次
MISSED_GRACE_SECONDS = 300


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def make_plan(action: str, force: bool, repeat: str, time_str: str,
              date: Optional[str] = None,
              weekdays: Iterable[int] = (),
              dates: Iterable[str] = ()) -> dict:
    return {
        "id": new_id(),
        "action": action,
        "force": bool(force),
        "repeat": repeat,
        "time": time_str,
        "date": date,
        "weekdays": sorted({int(w) % 7 for w in weekdays}),
        "dates": sorted({str(d) for d in dates}),
        "enabled": True,
        "created": _time.time(),
        "next_run": None,
    }


def parse_time(time_str) -> tuple:
    parts = str(time_str or "").split(":")
    try:
        hh = int(parts[0])
        mm = int(parts[1]) if len(parts) > 1 else 0
        ss = int(parts[2]) if len(parts) > 2 else 0
    except (ValueError, IndexError):
        return 0, 0, 0
    hh %= 24
    return hh, max(0, min(59, mm)), max(0, min(59, ss))


def _at(day: dt.date, time_str: str) -> dt.datetime:
    hh, mm, ss = parse_time(time_str)
    return dt.datetime(day.year, day.month, day.day, hh, mm, ss)


def cn_is_workday(day: dt.date) -> bool:
    """法定工作日：周末/法定假日为 False，调休补班的周末为 True。"""
    try:
        from chinese_calendar import is_workday
    except ImportError:
        return day.weekday() < 5
    try:
        return bool(is_workday(day))
    except Exception:
        # 当年数据尚未发布（chinese-calendar 每年 11 月更新）→ 退回普通工作日
        return day.weekday() < 5


def matches_day(plan: dict, day: dt.date) -> bool:
    repeat = plan.get("repeat") or REPEAT_ONCE
    if repeat == REPEAT_ONCE:
        return plan.get("date") == day.isoformat()
    if repeat == REPEAT_DAILY:
        return True
    if repeat == REPEAT_WEEKDAYS:
        return day.weekday() in (plan.get("weekdays") or [])
    if repeat == REPEAT_DATES:
        return day.isoformat() in (plan.get("dates") or [])
    if repeat == REPEAT_CN_WORKDAY:
        return cn_is_workday(day)
    return False


def compute_next_run(plan: dict,
                     now: Optional[dt.datetime] = None) -> Optional[dt.datetime]:
    """计算严格晚于 now 的下一次执行时刻；无法排程返回 None。"""
    now = now or dt.datetime.now()
    time_str = plan.get("time") or "00:00:00"
    repeat = plan.get("repeat") or REPEAT_ONCE

    if repeat == REPEAT_ONCE:
        if not plan.get("date"):
            return None
        try:
            day = dt.date.fromisoformat(str(plan["date"]))
        except ValueError:
            return None
        moment = _at(day, time_str)
        return moment if moment > now else None

    if repeat == REPEAT_DAILY:
        for offset in (0, 1):
            moment = _at(now.date() + dt.timedelta(days=offset), time_str)
            if moment > now:
                return moment
        return None

    if repeat == REPEAT_WEEKDAYS:
        days = set(plan.get("weekdays") or [])
        for offset in range(0, 8):
            day = now.date() + dt.timedelta(days=offset)
            if day.weekday() in days:
                moment = _at(day, time_str)
                if moment > now:
                    return moment
        return None

    if repeat == REPEAT_DATES:
        for iso in sorted(plan.get("dates") or []):
            try:
                day = dt.date.fromisoformat(str(iso))
            except ValueError:
                continue
            moment = _at(day, time_str)
            if moment > now:
                return moment
        return None

    if repeat == REPEAT_CN_WORKDAY:
        for offset in range(0, 61):
            day = now.date() + dt.timedelta(days=offset)
            if cn_is_workday(day):
                moment = _at(day, time_str)
                if moment > now:
                    return moment
        return None

    return None


def refresh_next_run(plan: dict,
                     now: Optional[dt.datetime] = None) -> Optional[float]:
    """把 plan["next_run"] 更新为下次执行时间戳（无法排程时为 None）。"""
    moment = compute_next_run(plan, now)
    plan["next_run"] = moment.timestamp() if moment else None
    return plan["next_run"]


def is_due(plan: dict, now_ts: Optional[float] = None) -> bool:
    """该计划此刻是否应触发（错过超过宽限期则不触发，由调用方跳到下一次）。"""
    if not plan.get("enabled", True):
        return False
    next_run = plan.get("next_run")
    if next_run is None:
        return False
    now_ts = _time.time() if now_ts is None else now_ts
    delta = now_ts - float(next_run)
    return 0 <= delta <= MISSED_GRACE_SECONDS


def is_stale(plan: dict, now_ts: Optional[float] = None) -> bool:
    """next_run 已过期且超出宽限期（需要跳过并重算）。"""
    next_run = plan.get("next_run")
    if next_run is None:
        return False
    now_ts = _time.time() if now_ts is None else now_ts
    return now_ts - float(next_run) > MISSED_GRACE_SECONDS


def describe_time(plan: dict) -> str:
    hh, mm, ss = parse_time(plan.get("time"))
    return "{:02d}:{:02d}:{:02d}".format(hh, mm, ss) if ss else \
        "{:02d}:{:02d}".format(hh, mm)


def describe(plan: dict) -> str:
    """规则的中文描述，例如"工作日 22:30"、"法定工作日 21:00"。"""
    repeat = plan.get("repeat") or REPEAT_ONCE
    moment = describe_time(plan)

    if repeat == REPEAT_ONCE:
        return "{} {}".format(plan.get("date") or "?", moment)
    if repeat == REPEAT_DAILY:
        return "每天 {}".format(moment)
    if repeat == REPEAT_WEEKDAYS:
        days = set(plan.get("weekdays") or [])
        if days == set(WEEKDAYS_SET):
            return "工作日 {}".format(moment)
        if days == set(range(7)):
            return "每天 {}".format(moment)
        if not days:
            return "未选星期 {}".format(moment)
        labels = [WEEKDAY_LABELS[i] for i in sorted(days)]
        return "{} {}".format("、".join(labels), moment)
    if repeat == REPEAT_DATES:
        labels = []
        for iso in sorted(plan.get("dates") or []):
            try:
                day = dt.date.fromisoformat(str(iso))
            except ValueError:
                continue
            labels.append("{}月{}日".format(day.month, day.day))
        if not labels:
            return "未选日期"
        return "{} {}".format("、".join(labels), moment)
    if repeat == REPEAT_CN_WORKDAY:
        return "法定工作日 {}".format(moment)
    return moment


def remove_executed(plan: dict, when: dt.date) -> None:
    """执行后清理：单次计划由调用方删除；指定日移除已执行日期。"""
    if (plan.get("repeat") or REPEAT_ONCE) == REPEAT_DATES:
        plan["dates"] = [d for d in plan.get("dates") or [] if d > when.isoformat()]
