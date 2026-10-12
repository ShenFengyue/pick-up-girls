"""Local, one-file-per-person JSON persistence."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JsonStore:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.load_errors: list[str] = []
        self._lock = threading.RLock()

    def _path(self, girl_id: str) -> Path:
        if not girl_id or any(char not in "0123456789abcdef-" for char in girl_id.lower()):
            raise ValueError("人物编号无效")
        return self.directory / f"{girl_id}.json"

    def _write(self, girl: dict[str, Any]) -> None:
        girl["updated_at"] = now_iso()
        path = self._path(girl["id"])
        fd, temp_name = tempfile.mkstemp(prefix=f".{girl['id']}.", suffix=".tmp", dir=self.directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                json.dump(girl, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    def create_girl(self, profile: dict[str, Any], affection: float = 5.0) -> dict[str, Any]:
        if not 18 <= int(profile.get("age", 0)) <= 100:
            raise ValueError("角色年龄必须在 18 至 100 岁之间")
        if not 0 <= float(affection) <= 10:
            raise ValueError("好感度必须在 0 至 10 之间")
        with self._lock:
            girl_id = uuid.uuid4().hex[:12]
            while self._path(girl_id).exists():
                girl_id = uuid.uuid4().hex[:12]
            timestamp = now_iso()
            girl = {
                "schema_version": 1, "id": girl_id, "created_at": timestamp, "updated_at": timestamp,
                "profile": dict(profile), "affection": round(float(affection), 1),
                "status": "active", "relationship_memory": {"facts": [], "preferences": [], "milestones": []}, "messages": [], "reviews": [],
                "events": [], "topic_requests": 0, "last_reviewed_message_count": 0,
            }
            self._write(girl)
            return girl

    def get_girl(self, girl_id: str) -> dict[str, Any]:
        path = self._path(girl_id)
        try:
            with self._lock, path.open("r", encoding="utf-8") as handle:
                girl = json.load(handle)
        except FileNotFoundError as exc:
            raise KeyError(f"找不到人物档案：{girl_id}") from exc
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError(f"人物档案损坏，无法读取：{girl_id}") from exc
        if not isinstance(girl, dict) or girl.get("id") != girl_id or not isinstance(girl.get("profile"), dict):
            raise ValueError(f"人物档案格式不正确：{girl_id}")
        return girl

    def save_girl(self, girl: dict[str, Any]) -> None:
        if not 0 <= float(girl.get("affection", -1)) <= 10:
            raise ValueError("好感度必须在 0 至 10 之间")
        with self._lock:
            self._write(girl)

    def list_girls(self) -> list[dict[str, Any]]:
        self.load_errors.clear()
        girls = []
        for path in self.directory.glob("*.json"):
            try:
                girls.append(self.get_girl(path.stem))
            except (KeyError, ValueError) as exc:
                self.load_errors.append(f"{path.name}：{exc}")
        return sorted(girls, key=lambda item: item.get("updated_at", ""), reverse=True)

    def append_message(self, girl_id: str, role: str, content: str) -> dict[str, Any]:
        if role not in {"user", "assistant", "system"}:
            raise ValueError("消息角色无效")
        if not content.strip():
            raise ValueError("消息不能为空")
        with self._lock:
            girl = self.get_girl(girl_id)
            message = {"id": uuid.uuid4().hex, "role": role, "content": content.strip(), "created_at": now_iso()}
            girl.setdefault("messages", []).append(message)
            self._write(girl)
            return message

    def update(self, girl_id: str, updater) -> dict[str, Any]:
        with self._lock:
            girl = self.get_girl(girl_id)
            updater(girl)
            self._write(girl)
            return girl
