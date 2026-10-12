"""Create realistic adult character profiles from short descriptions."""

from __future__ import annotations

import random
from typing import Any

from services.deepseek_client import AIServiceError

PROFILE_FIELDS = ("name", "age", "city", "occupation", "background", "personality", "interests", "communication_style", "values", "boundaries", "current_life", "first_impression")


class CharacterService:
    def __init__(self, ai_client):
        self.ai = ai_client

    def _profile(self, data: dict[str, Any]) -> tuple[dict[str, Any], float]:
        missing = [field for field in PROFILE_FIELDS if field not in data]
        if missing:
            raise AIServiceError("角色资料不完整，请重试生成。")
        try:
            age = int(data["age"])
            affection = float(data.get("initial_affection", 5.0))
        except (TypeError, ValueError) as exc:
            raise AIServiceError("角色年龄或初始好感度格式无效，请重试。") from exc
        if age < 18 or age > 100:
            raise AIServiceError("生成的人物未满足成年年龄要求，请重试。")
        if not 0 <= affection <= 10:
            raise AIServiceError("模型给出的初始好感度无效，请重试。")
        profile = {field: data[field] for field in PROFILE_FIELDS}
        if not isinstance(profile["interests"], list):
            raise AIServiceError("角色兴趣字段格式无效，请重试。")
        for field in PROFILE_FIELDS:
            if field != "interests" and not isinstance(profile[field], (str, int)):
                raise AIServiceError("角色资料字段格式无效，请重试。")
        profile["age"] = age
        profile["interests"] = [str(value) for value in profile["interests"][:12]]
        return profile, max(0, min(10, affection))

    def create_from_description(self, description: str) -> tuple[dict[str, Any], float]:
        if not description.strip():
            raise ValueError("请先简单描述你想认识的人")
        data = self.ai.json_completion([
            {"role": "system", "content": "你为现实社交练习创建有自主性、真实可信的成年女性角色。只输出 JSON 对象，字段：name,age,city,occupation,background,personality,interests(array),communication_style,values,boundaries,current_life,first_impression,initial_affection(number 0-10)。年龄必须至少18岁。不要生成迎合用户的理想伴侣，保持多样和内在一致。"},
            {"role": "user", "content": description[:4000]},
        ])
        return self._profile(data)

    def create_random(self) -> tuple[dict[str, Any], float]:
        seed = random.SystemRandom().randint(1, 2_000_000_000)
        data = self.ai.json_completion([
            {"role": "system", "content": "你为现实社交练习创建有自主性、真实可信的成年女性角色。只输出 JSON 对象，字段：name,age,city,occupation,background,personality,interests(array),communication_style,values,boundaries,current_life,first_impression,initial_affection(number 0-10)。年龄必须至少18岁。角色需要具体、自然、多样、不刻板，有自己的生活和边界。"},
            {"role": "user", "content": f"请随机创作一个全新人物，随机种子：{seed}。"},
        ])
        return self._profile(data)
