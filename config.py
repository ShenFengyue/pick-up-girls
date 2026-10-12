"""集中配置：模型、请求参数、成本估算与预算。"""

from __future__ import annotations

# 模型与请求
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"
DEEPSEEK_TIMEOUT = 45          # 单次请求超时（秒）
DEEPSEEK_MAX_RETRIES = 1       # 连接层自动重试次数
DEEPSEEK_TEMPERATURE = 1.0     # 采样温度，DeepSeek 默认 1.0

# 成本估算（人民币 / 每百万 tokens）。DeepSeek 会不定期调整计价，
# 这里是估算值，按需修改即可。
INPUT_PRICE_PER_MTOKEN = 1.0
OUTPUT_PRICE_PER_MTOKEN = 2.0
CURRENCY = "¥"

# 预算与限额
MONTHLY_BUDGET = 100.0   # 月度预算提醒阈值（0 表示关闭提醒）
DAILY_TOPIC_LIMIT = 5    # 每天「让 AI 找话题」的次数上限


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return round(
        input_tokens / 1_000_000 * INPUT_PRICE_PER_MTOKEN
        + output_tokens / 1_000_000 * OUTPUT_PRICE_PER_MTOKEN,
        6,
    )
