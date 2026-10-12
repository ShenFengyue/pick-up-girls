from services.memory_service import MAX_PER_CATEGORY, merge_memory, normalize_memory, render_memory


def test_merge_accumulates_without_replacing():
    existing = {"facts": ["用户喜欢看展"], "preferences": [], "milestones": []}
    incoming = {"facts": ["用户是杭州人"], "preferences": ["喜欢安静的约会"], "milestones": ["交换了联系方式"]}
    merged, added = merge_memory(existing, incoming)
    assert merged["facts"] == ["用户喜欢看展", "用户是杭州人"]
    assert merged["preferences"] == ["喜欢安静的约会"]
    assert merged["milestones"] == ["交换了联系方式"]
    assert added["facts"] == ["用户是杭州人"]


def test_merge_deduplicates_whitespace_and_case():
    existing = {"facts": ["用户喜欢看展"], "preferences": [], "milestones": []}
    incoming = {"facts": ["用户喜欢看展 ", "用户是杭州人"], "preferences": [], "milestones": []}
    merged, added = merge_memory(existing, incoming)
    assert merged["facts"] == ["用户喜欢看展", "用户是杭州人"]
    assert added["facts"] == ["用户是杭州人"]


def test_legacy_string_memory_is_preserved():
    merged, added = merge_memory("用户喜欢看展；不爱熬夜。", {"facts": ["用户是杭州人"], "preferences": [], "milestones": []})
    assert merged["facts"] == ["用户喜欢看展；不爱熬夜。", "用户是杭州人"]
    assert added["facts"] == ["用户是杭州人"]


def test_merge_keeps_recent_entries_when_over_limit():
    existing = {"facts": [f"旧事实{i}" for i in range(MAX_PER_CATEGORY)], "preferences": [], "milestones": []}
    incoming = {"facts": ["最新事实"], "preferences": [], "milestones": []}
    merged, _ = merge_memory(existing, incoming)
    assert len(merged["facts"]) == MAX_PER_CATEGORY
    assert merged["facts"][-1] == "最新事实"
    assert "旧事实0" not in merged["facts"]


def test_normalize_memory_filters_invalid_entries():
    memory = normalize_memory({
        "facts": ["用户喜欢看展", "", 123, None],
        "preferences": "不是列表",
        "milestones": ["交换了联系方式", "交换了联系方式"],
    })
    assert memory["facts"] == ["用户喜欢看展"]
    assert memory["preferences"] == []
    assert memory["milestones"] == ["交换了联系方式"]


def test_render_memory_lists_only_non_empty_categories():
    rendered = render_memory({"facts": ["用户喜欢看展"], "preferences": [], "milestones": ["交换了联系方式"]})
    assert "关于彼此的事实" in rendered
    assert "关系节点" in rendered
    assert "偏好与好恶" not in rendered
