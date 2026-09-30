"""core.planner 规则引擎单元测试。"""
import datetime as dt

from poweroff.core import planner


def test_daily_next_run_same_and_next_day():
    plan = planner.make_plan("shutdown", True, planner.REPEAT_DAILY, "22:30:00")
    assert planner.compute_next_run(
        plan, dt.datetime(2026, 9, 30, 10, 0)) == dt.datetime(2026, 9, 30, 22, 30)
    assert planner.compute_next_run(
        plan, dt.datetime(2026, 9, 30, 23, 0)) == dt.datetime(2026, 10, 1, 22, 30)


def test_weekdays_friday_night_goes_to_monday():
    plan = planner.make_plan("shutdown", True, planner.REPEAT_WEEKDAYS,
                             "21:00", weekdays=[0, 1, 2, 3, 4])
    # 2026-10-02 是周五
    assert planner.compute_next_run(
        plan, dt.datetime(2026, 10, 2, 22, 0)) == dt.datetime(2026, 10, 5, 21, 0)


def test_dates_are_sorted_and_skipped():
    plan = planner.make_plan("shutdown", True, planner.REPEAT_DATES, "08:00",
                             dates=["2026-10-08", "2026-10-01"])
    assert planner.compute_next_run(
        plan, dt.datetime(2026, 9, 30, 12, 0)) == dt.datetime(2026, 10, 1, 8, 0)
    assert planner.compute_next_run(
        plan, dt.datetime(2026, 10, 2, 12, 0)) == dt.datetime(2026, 10, 8, 8, 0)
    assert planner.compute_next_run(
        plan, dt.datetime(2026, 10, 9, 0, 0)) is None


def test_once_expires():
    plan = planner.make_plan("shutdown", True, planner.REPEAT_ONCE, "22:00",
                             date="2026-10-01")
    assert planner.compute_next_run(
        plan, dt.datetime(2026, 10, 1, 21, 0)) == dt.datetime(2026, 10, 1, 22, 0)
    assert planner.compute_next_run(plan, dt.datetime(2026, 10, 2)) is None


def test_cn_workday_skips_national_day():
    # 2026-10-01~10-07 国庆假期（chinese-calendar 数据），下一工作日 10-08
    plan = planner.make_plan("shutdown", True, planner.REPEAT_CN_WORKDAY, "12:00")
    nxt = planner.compute_next_run(plan, dt.datetime(2026, 9, 30, 13, 0))
    assert nxt == dt.datetime(2026, 10, 8, 12, 0)
    assert planner.cn_is_workday(dt.date(2026, 10, 1)) is False
    assert planner.cn_is_workday(dt.date(2026, 9, 30)) is True


def test_is_due_within_grace_only():
    plan = planner.make_plan("shutdown", True, planner.REPEAT_DAILY, "22:30")
    planner.refresh_next_run(plan, dt.datetime(2026, 9, 30, 22, 0))
    due_ts = plan["next_run"]
    assert planner.is_due(plan, due_ts + 60) is True
    assert planner.is_due(plan, due_ts + planner.MISSED_GRACE_SECONDS + 1) is False
    assert planner.is_stale(plan, due_ts + planner.MISSED_GRACE_SECONDS + 1) is True
    assert planner.is_due(plan, due_ts - 5) is False


def test_disabled_plan_never_due():
    plan = planner.make_plan("shutdown", True, planner.REPEAT_DAILY, "22:30")
    planner.refresh_next_run(plan, dt.datetime(2026, 9, 30, 22, 0))
    plan["enabled"] = False
    assert planner.is_due(plan, plan["next_run"] + 1) is False


def test_describe_variants():
    assert planner.describe(planner.make_plan(
        "shutdown", True, planner.REPEAT_DAILY, "23:00")) == "每天 23:00"
    assert planner.describe(planner.make_plan(
        "shutdown", True, planner.REPEAT_WEEKDAYS, "21:00",
        weekdays=[0, 1, 2, 3, 4])) == "工作日 21:00"
    assert planner.describe(planner.make_plan(
        "shutdown", True, planner.REPEAT_WEEKDAYS, "21:00",
        weekdays=[5, 6])) == "周六、周日 21:00"
    assert planner.describe(planner.make_plan(
        "shutdown", True, planner.REPEAT_DATES, "20:00",
        dates=["2026-10-01", "2026-12-25"])) == "10月1日、12月25日 20:00"
    assert planner.describe(planner.make_plan(
        "shutdown", True, planner.REPEAT_CN_WORKDAY, "21:30")) == "法定工作日 21:30"
    assert planner.describe(planner.make_plan(
        "shutdown", True, planner.REPEAT_ONCE, "22:00",
        date="2026-11-11")) == "2026-11-11 22:00"


def test_remove_executed_dates():
    plan = planner.make_plan("shutdown", True, planner.REPEAT_DATES, "20:00",
                             dates=["2026-09-30", "2026-10-08"])
    planner.remove_executed(plan, dt.date(2026, 9, 30))
    assert plan["dates"] == ["2026-10-08"]
