from services.relationship_service import apply_affection_change, request_topic_penalty


def test_topic_request_always_costs_one_and_records_event():
    girl = {"affection": 1, "topic_requests": 0, "events": [], "status": "active"}
    request_topic_penalty(girl)
    request_topic_penalty(girl)
    assert girl["affection"] == 0
    assert girl["topic_requests"] == 2
    assert len(girl["events"]) == 2
    assert girl["status"] == "eliminated"


def test_affection_changes_are_bounded_and_clamped():
    girl = {"affection": 9.5, "status": "active", "events": []}
    apply_affection_change(girl, 8, "尊重了对方的边界")
    assert girl["affection"] == 10
    assert girl["events"][-1]["delta"] == 0.5


def test_zero_affection_ends_relationship_without_deleting_history():
    girl = {"affection": 0.5, "status": "active", "messages": [{"content": "历史"}], "events": []}
    apply_affection_change(girl, -2, "持续施压")
    assert girl["status"] == "eliminated"
    assert girl["messages"] == [{"content": "历史"}]
