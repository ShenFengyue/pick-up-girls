from storage.json_store import JsonStore


def profile(name="林知夏"):
    return {
        "name": name, "age": 24, "city": "杭州", "occupation": "插画师",
        "background": "在杭州长大，大学学习视觉设计。", "personality": "安静而幽默",
        "interests": ["展览", "散步"], "communication_style": "慢热直接",
        "values": "重视真诚", "boundaries": "不喜欢被催促",
        "current_life": "最近项目较多", "first_impression": "在画展认识",
    }


def test_each_girl_has_an_independent_persistent_file(tmp_path):
    store = JsonStore(tmp_path)
    first = store.create_girl(profile())
    second = store.create_girl(profile("周宁"))

    store.append_message(first["id"], "user", "我喜欢看展")
    assert store.get_girl(first["id"])["messages"][0]["content"] == "我喜欢看展"
    assert store.get_girl(second["id"])["messages"] == []
    assert len(list(tmp_path.glob("*.json"))) == 2


def test_corrupt_file_does_not_hide_other_profiles(tmp_path):
    store = JsonStore(tmp_path)
    girl = store.create_girl(profile())
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")

    assert [item["id"] for item in store.list_girls()] == [girl["id"]]
    assert len(store.load_errors) == 1
