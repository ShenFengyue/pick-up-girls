"""Persistent roleplay, topic suggestions and end-of-session review."""

from __future__ import annotations

import json

import config
from services.memory_service import merge_memory, render_memory
from services.relationship_service import apply_affection_change, request_topic_penalty


def _profile_text(profile: dict) -> str:
    return json.dumps(profile, ensure_ascii=False)


class ConversationService:
    def __init__(self, store, ai_client, usage=None):
        self.store = store
        self.ai = ai_client
        self.usage = usage

    def _context(self, girl: dict, message_limit: int = 24, char_limit: int = 14000) -> list[dict[str, str]]:
        profile = girl["profile"]
        system = (
            "你正在进行现实社交模拟。你必须始终扮演档案中的成年女性，不做助手、不点评用户、不提供教练式反馈。"
            "保持真实、自主、平等、尊重边界；表达长度接近日常聊天，可以简短、冷淡、好奇、幽默或自然结束。"
            "不要因套路自动增加好感，也不要编造未发生的共同经历。结合人物性格、生活、关系记忆和完整互动。"
            f"\n人物档案：{_profile_text(profile)}\n当前好感度：{girl['affection']}/10。"
            f"\n长期关系记忆：{render_memory(girl.get('relationship_memory')) or '暂无'}"
        )
        messages = [{"role": "system", "content": system}]
        selected = []
        total = 0
        for message in reversed(girl.get("messages", [])[-message_limit:]):
            content = str(message.get("content", ""))
            if total + len(content) > char_limit:
                break
            total += len(content)
            selected.append({"role": "assistant" if message.get("role") == "assistant" else "user", "content": content})
        messages.extend(reversed(selected))
        return messages

    def send_message(self, girl_id: str, content: str) -> str:
        self.save_user_message(girl_id, content)
        return self.reply_to_latest_user_message(girl_id)

    def save_user_message(self, girl_id: str, content: str) -> dict:
        girl = self.store.get_girl(girl_id)
        if girl.get("status") != "active":
            raise ValueError("这段关系已经结束，只能查看历史记录。")
        if not content.strip():
            raise ValueError("消息不能为空")
        return self.store.append_message(girl_id, "user", content)

    def reply_to_latest_user_message(self, girl_id: str) -> str:
        girl = self.store.get_girl(girl_id)
        if girl.get("status") != "active":
            raise ValueError("这段关系已经结束，只能查看历史记录。")
        messages = girl.get("messages", [])
        if not messages or messages[-1].get("role") != "user":
            raise ValueError("没有等待回复的用户消息。")
        reply = self.ai.complete(self._context(girl))
        self.store.append_message(girl_id, "assistant", reply)
        return reply

    def suggest_topic(self, girl_id: str) -> str:
        if self.usage is not None and self.usage.today_topic_count() >= config.DAILY_TOPIC_LIMIT:
            raise ValueError(f"今天的话题建议次数已用完（每日上限 {config.DAILY_TOPIC_LIMIT} 次），明天再来吧。")
        girl = self.store.get_girl(girl_id)
        if girl.get("status") != "active":
            raise ValueError("这段关系已经结束，不能继续请求话题。")
        self.store.update(girl_id, request_topic_penalty)
        if self.usage is not None:
            self.usage.record_topic_request()
        girl = self.store.get_girl(girl_id)
        prompt = self._context(girl)
        prompt[0]["content"] += "\n用户请求一个自然的话题切入建议。只给用户一个简短、开放、结合当前情境的建议，不要替用户发送。"
        return self.ai.complete(prompt)

    def end_chat_and_review(self, girl_id: str) -> dict:
        girl = self.store.get_girl(girl_id)
        messages = girl.get("messages", [])
        start = int(girl.get("last_reviewed_message_count", 0))
        session = messages[start:]
        if not session:
            raise ValueError("本次还没有新的聊天内容可供复盘。")
        transcript = "\n".join(f"{'用户' if m['role'] == 'user' else '她'}：{m['content']}" for m in session)
        raw = self.ai.json_completion([
            {"role": "system", "content": "你是务实、尊重双方主体性的社交复盘教练。基于实际对话生成JSON，字段：summary(str), strengths(array of {evidence,reason}), improvements(array of {evidence,reason,alternative}), relationship_change(str), affection_delta(number between -2 and 2), reason(str), memory(object)。memory 分三类，都是字符串数组：facts（关于用户与这段关系、能影响后续交流的稳定事实）、preferences（双方明确表达过的偏好与好恶）、milestones（关系进展、重要承诺或节点）。只记录这次对话里新出现、且未来互动仍重要的信息；不要重复既有记忆，不要推断未经表达的信息。避免操控建议，具体、简洁、不过度批评或夸奖。"},
            {"role": "user", "content": f"人物档案：{_profile_text(girl['profile'])}\n好感度：{girl['affection']}\n既有记忆：{render_memory(girl.get('relationship_memory')) or '暂无'}\n本次对话：\n{transcript[-12000:]}"},
        ])
        required = ("summary", "strengths", "improvements", "relationship_change", "affection_delta", "reason", "memory")
        if any(field not in raw for field in required) or not isinstance(raw["strengths"], list) or not isinstance(raw["improvements"], list):
            raise ValueError("复盘内容格式异常，请重试。")
        if raw.get("memory") is not None and not isinstance(raw["memory"], (dict, str)):
            raise ValueError("复盘长期记忆格式异常，请重试。")
        try:
            delta = max(-2.0, min(2.0, float(raw["affection_delta"])))
        except (TypeError, ValueError) as exc:
            raise ValueError("复盘好感度变化格式异常，请重试。") from exc
        result = self.store.update(girl_id, lambda current: self._save_review(current, raw, delta, len(messages)))
        return result["reviews"][-1]

    @staticmethod
    def _save_review(girl: dict, raw: dict, delta: float, message_count: int) -> None:
        before = float(girl["affection"])
        applied = apply_affection_change(girl, delta, str(raw["reason"])[:500])
        after = float(girl["affection"])
        merged, added = merge_memory(girl.get("relationship_memory"), raw.get("memory"))
        girl["relationship_memory"] = merged
        review = {
            "summary": str(raw["summary"])[:2000], "strengths": raw["strengths"][:10],
            "improvements": raw["improvements"][:10], "relationship_change": str(raw["relationship_change"])[:2000],
            "affection_before": before, "affection_after": after, "affection_delta": applied,
            "reason": str(raw["reason"])[:1000], "memory": render_memory(added),
        }
        girl.setdefault("reviews", []).append(review)
        girl["last_reviewed_message_count"] = message_count
