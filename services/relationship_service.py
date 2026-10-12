"""Deterministic relationship state rules."""


def apply_affection_change(girl: dict, delta: float, reason: str) -> float:
    delta = max(-2.0, min(2.0, float(delta)))
    before = float(girl["affection"])
    after = round(max(0.0, min(10.0, before + delta)), 1)
    applied = round(after - before, 1)
    girl["affection"] = after
    girl.setdefault("events", []).append({"type": "affection_change", "before": before, "after": after, "delta": applied, "reason": reason})
    if after <= 0:
        girl["status"] = "eliminated"
    return applied


def request_topic_penalty(girl: dict) -> None:
    before = float(girl["affection"])
    after = round(max(0.0, before - 1.0), 1)
    girl["affection"] = after
    girl["topic_requests"] = int(girl.get("topic_requests", 0)) + 1
    girl.setdefault("events", []).append({"type": "topic_request", "before": before, "after": after, "delta": round(after - before, 1), "reason": "请求 AI 提供话题"})
    if after <= 0:
        girl["status"] = "eliminated"
