"""DeepSeek client using the OpenAI-compatible API."""

from __future__ import annotations

import json
import os
from typing import Any

import config
from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI, RateLimitError


class AIServiceError(RuntimeError):
    pass


class DeepSeekClient:
    def __init__(self, api_key: str | None = None, usage_tracker=None):
        key = (api_key if api_key is not None else os.getenv("DEEPSEEK_API_KEY", "")).strip()
        self.client = (
            OpenAI(
                api_key=key,
                base_url=config.DEEPSEEK_BASE_URL,
                timeout=config.DEEPSEEK_TIMEOUT,
                max_retries=config.DEEPSEEK_MAX_RETRIES,
            )
            if key
            else None
        )
        self.usage_tracker = usage_tracker

    def complete(self, messages: list[dict[str, str]], *, json_mode: bool = False) -> str:
        if self.client is None:
            raise AIServiceError("请在侧边栏保存 DeepSeek API Key，或临时选择使用本机环境变量。")
        try:
            response = self.client.chat.completions.create(
                model=config.DEEPSEEK_MODEL,
                messages=messages,
                temperature=config.DEEPSEEK_TEMPERATURE,
                response_format={"type": "json_object"} if json_mode else None,
            )
            content = response.choices[0].message.content
            if not content:
                raise AIServiceError("模型返回了空内容，请重试。")
            usage = getattr(response, "usage", None)
            if usage is not None and self.usage_tracker is not None:
                input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
                if input_tokens or output_tokens:
                    self.usage_tracker.record_usage(input_tokens, output_tokens)
            return content
        except AuthenticationError as exc:
            raise AIServiceError("DeepSeek 鉴权失败，请检查 API Key。") from exc
        except RateLimitError as exc:
            raise AIServiceError("DeepSeek 请求受限或余额不足，请检查账户额度后重试。") from exc
        except APIConnectionError as exc:
            raise AIServiceError("无法连接 DeepSeek，请检查网络后重试。") from exc
        except APIStatusError as exc:
            if exc.status_code == 402:
                raise AIServiceError("DeepSeek 账户余额不足，请充值或检查可用额度。") from exc
            raise AIServiceError(f"DeepSeek 请求失败（HTTP {exc.status_code}），请稍后重试。") from exc
        except AIServiceError:
            raise
        except Exception as exc:
            raise AIServiceError("DeepSeek 返回异常，请稍后重试。") from exc

    def json_completion(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        raw = self.complete(messages, json_mode=True)
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AIServiceError("模型返回格式异常，请重试。") from exc
        if not isinstance(parsed, dict):
            raise AIServiceError("模型返回格式异常，请重试。")
        return parsed
