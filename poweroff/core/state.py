"""计划状态持久化：单次倒计时计划与重复计划列表共存，兼容旧版格式。

文档结构（version 2）::

    {"version": 2, "immediate": {...} | null, "plans": [{...}, ...]}

旧版文件直接保存单次计划字段（无 version 键），读取时自动迁移。
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Optional

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PowerOff")
STATE_FILE = os.path.join(APP_DIR, "state.json")

DOC_VERSION = 2


@dataclass
class PlanState:
    action: str
    force: bool
    backend: str
    deadline: float
    created: float


def _fresh_doc() -> dict:
    return {"version": DOC_VERSION, "immediate": None, "plans": []}


def _load_doc() -> dict:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError):
        return _fresh_doc()
    if not isinstance(raw, dict):
        return _fresh_doc()
    if "version" not in raw:
        # 旧版格式：整个文档就是单次计划
        immediate = raw if ("action" in raw and "deadline" in raw) else None
        return {"version": DOC_VERSION, "immediate": immediate, "plans": []}
    plans = raw.get("plans")
    return {
        "version": DOC_VERSION,
        "immediate": raw.get("immediate"),
        "plans": plans if isinstance(plans, list) else [],
    }


def _save_doc(doc: dict) -> None:
    os.makedirs(APP_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(doc, handle, ensure_ascii=False, indent=2)


def _remove_file() -> None:
    try:
        os.remove(STATE_FILE)
    except OSError:
        pass


def _parse_immediate(raw) -> Optional[PlanState]:
    if not isinstance(raw, dict):
        return None
    try:
        return PlanState(
            action=str(raw["action"]),
            force=bool(raw["force"]),
            backend=str(raw["backend"]),
            deadline=float(raw["deadline"]),
            created=float(raw["created"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def save_state(state: PlanState) -> None:
    """写入单次倒计时计划，保留已有的重复计划列表。"""
    doc = _load_doc()
    doc["immediate"] = asdict(state)
    _save_doc(doc)


def load_state() -> Optional[PlanState]:
    return _parse_immediate(_load_doc()["immediate"])


def clear_state() -> None:
    """清除单次倒计时计划；若重复计划列表也为空则删除整个文件。"""
    doc = _load_doc()
    doc["immediate"] = None
    if not doc["plans"]:
        _remove_file()
        return
    _save_doc(doc)


def save_plans(plans: list) -> None:
    """写入重复计划列表，保留单次计划。"""
    doc = _load_doc()
    doc["plans"] = [p for p in plans if isinstance(p, dict)]
    if doc["immediate"] is None and not doc["plans"]:
        _remove_file()
        return
    _save_doc(doc)


def load_plans() -> list:
    doc = _load_doc()
    result = []
    for item in doc["plans"]:
        if isinstance(item, dict) and "id" in item and "repeat" in item:
            result.append(item)
    return result
