"""Persistent, app-wide usage and cost tracking (daily aggregates)."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import config

BEIJING_TIMEZONE = timezone(timedelta(hours=8), "北京时间")


def _now() -> datetime:
    return datetime.now(BEIJING_TIMEZONE)


def _today_key() -> str:
    return _now().strftime("%Y-%m-%d")


def _month_prefix() -> str:
    return _now().strftime("%Y-%m")


def _empty_day() -> dict[str, float | int]:
    return {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0, "topic_requests": 0}


class UsageStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self.session = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0}

    def _load(self) -> dict[str, Any]:
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return {"days": {}}
        except (json.JSONDecodeError, OSError):
            return {"days": {}}
        if not isinstance(data, dict) or not isinstance(data.get("days"), dict):
            return {"days": {}}
        return data

    def _write(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix=".usage.", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def record_usage(self, input_tokens: int, output_tokens: int) -> None:
        cost = config.estimate_cost(int(input_tokens), int(output_tokens))
        with self._lock:
            self.session["calls"] += 1
            self.session["input_tokens"] += int(input_tokens)
            self.session["output_tokens"] += int(output_tokens)
            self.session["cost"] = round(self.session["cost"] + cost, 6)
            data = self._load()
            day = data.setdefault("days", {}).setdefault(_today_key(), _empty_day())
            day["calls"] = int(day.get("calls", 0)) + 1
            day["input_tokens"] = int(day.get("input_tokens", 0)) + int(input_tokens)
            day["output_tokens"] = int(day.get("output_tokens", 0)) + int(output_tokens)
            day["cost"] = round(float(day.get("cost", 0.0)) + cost, 6)
            self._write(data)

    def record_topic_request(self) -> None:
        with self._lock:
            data = self._load()
            day = data.setdefault("days", {}).setdefault(_today_key(), _empty_day())
            day["topic_requests"] = int(day.get("topic_requests", 0)) + 1
            self._write(data)

    def session_totals(self) -> dict[str, int | float]:
        with self._lock:
            return dict(self.session)

    def month_totals(self) -> dict[str, int | float]:
        with self._lock:
            data = self._load()
            prefix = _month_prefix()
            totals: dict[str, int | float] = {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0}
            for key, day in data.get("days", {}).items():
                if key.startswith(prefix):
                    totals["calls"] += int(day.get("calls", 0))
                    totals["input_tokens"] += int(day.get("input_tokens", 0))
                    totals["output_tokens"] += int(day.get("output_tokens", 0))
                    totals["cost"] = round(totals["cost"] + float(day.get("cost", 0.0)), 6)
            return totals

    def today_topic_count(self) -> int:
        with self._lock:
            data = self._load()
            return int(data.get("days", {}).get(_today_key(), {}).get("topic_requests", 0))
