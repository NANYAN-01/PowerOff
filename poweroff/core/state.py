"""计划状态持久化：程序重启后可恢复倒计时显示与本地执行。"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Optional

APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "PowerOff")
STATE_FILE = os.path.join(APP_DIR, "state.json")


@dataclass
class PlanState:
    action: str
    force: bool
    backend: str
    deadline: float
    created: float


def save_state(state: PlanState) -> None:
    os.makedirs(APP_DIR, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as handle:
        json.dump(asdict(state), handle, ensure_ascii=False, indent=2)


def load_state() -> Optional[PlanState]:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, ValueError):
        return None
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


def clear_state() -> None:
    try:
        os.remove(STATE_FILE)
    except OSError:
        pass
