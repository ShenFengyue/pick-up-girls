import pytest

import config
from services.conversation_service import ConversationService
from storage.usage_store import UsageStore


def test_estimate_cost_formula():
    assert config.estimate_cost(0, 0) == 0.0
    assert config.estimate_cost(1_000_000, 0) == 1.0
    assert config.estimate_cost(0, 1_000_000) == 2.0
    assert config.estimate_cost(1_000_000, 1_000_000) == 3.0


def test_record_usage_accumulates_session_and_month(tmp_path):
    usage = UsageStore(tmp_path / "usage.json")
    usage.record_usage(1_000_000, 1_000_000)
    usage.record_usage(1_000_000, 1_000_000)
    assert usage.session_totals() == {"calls": 2, "input_tokens": 2_000_000, "output_tokens": 2_000_000, "cost": 6.0}
    assert usage.month_totals() == {"calls": 2, "input_tokens": 2_000_000, "output_tokens": 2_000_000, "cost": 6.0}


def test_topic_request_counting(tmp_path):
    usage = UsageStore(tmp_path / "usage.json")
    usage.record_topic_request()
    usage.record_topic_request()
    assert usage.today_topic_count() == 2


def test_month_totals_ignore_other_months(tmp_path):
    usage = UsageStore(tmp_path / "usage.json")
    data = usage._load()
    data["days"]["2000-01-01"] = {"calls": 9, "input_tokens": 100, "output_tokens": 100, "cost": 9.0, "topic_requests": 1}
    usage._write(data)
    assert usage.month_totals() == {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0.0}


class FakeAI:
    def complete(self, context):
        return "话题建议"

    def json_completion(self, messages):
        return {}


class FakeUsage:
    def __init__(self, topic_count):
        self.topic_count = topic_count

    def today_topic_count(self):
        return self.topic_count

    def record_topic_request(self):
        self.topic_count += 1


def test_topic_daily_limit_blocks_when_reached():
    service = ConversationService(None, FakeAI(), FakeUsage(config.DAILY_TOPIC_LIMIT))
    with pytest.raises(ValueError):
        service.suggest_topic("任意编号")
