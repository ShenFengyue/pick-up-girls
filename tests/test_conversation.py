from services.conversation_service import ConversationService


class FakeAI:
    def __init__(self, response=None, failure=None):
        self.response = response
        self.failure = failure

    def complete(self, context):
        if self.failure:
            raise self.failure
        return self.response

    def json_completion(self, messages):
        return {"summary": "聊了兴趣", "strengths": [], "improvements": [], "relationship_change": "自然", "affection_delta": 0.2, "reason": "双方分享了兴趣", "memory": {"facts": ["用户喜欢看展"], "preferences": [], "milestones": []}}


def new_girl(store):
    return store.create_girl({"name": "林知夏", "age": 24, "city": "杭州", "occupation": "插画师", "background": "", "personality": "", "interests": [], "communication_style": "", "values": "", "boundaries": "", "current_life": "", "first_impression": ""})


def test_chat_saves_both_messages_and_review_updates_memory(tmp_path):
    from storage.json_store import JsonStore
    store = JsonStore(tmp_path)
    girl = new_girl(store)
    service = ConversationService(store, FakeAI("我最近也去看了展。"))

    service.send_message(girl["id"], "你最近看展了吗？")
    assert [m["role"] for m in store.get_girl(girl["id"])["messages"]] == ["user", "assistant"]
    result = service.end_chat_and_review(girl["id"])
    saved = store.get_girl(girl["id"])
    assert result["affection_after"] == 5.2
    assert saved["relationship_memory"] == {"facts": ["用户喜欢看展"], "preferences": [], "milestones": []}
    assert len(saved["reviews"]) == 1


def test_api_failure_keeps_user_message_saved(tmp_path):
    from storage.json_store import JsonStore
    store = JsonStore(tmp_path)
    girl = new_girl(store)
    service = ConversationService(store, FakeAI(failure=RuntimeError("offline")))

    try:
        service.send_message(girl["id"], "你好")
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected API failure")
    assert len(store.get_girl(girl["id"])["messages"]) == 1


def test_topic_request_cost_is_saved_even_when_ai_fails(tmp_path):
    from storage.json_store import JsonStore
    store = JsonStore(tmp_path)
    girl = new_girl(store)
    store.update(girl["id"], lambda item: item.update(affection=1.0))
    service = ConversationService(store, FakeAI(failure=RuntimeError("offline")))

    try:
        service.suggest_topic(girl["id"])
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected API failure")
    saved = store.get_girl(girl["id"])
    assert saved["affection"] == 0
    assert saved["topic_requests"] == 1
    assert saved["status"] == "eliminated"
