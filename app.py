from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from services.character_service import CharacterService
from services.conversation_service import ConversationService
from services.credential_store import CredentialStoreError, delete_saved_api_key, get_saved_api_key, save_api_key
from services.deepseek_client import AIServiceError, DeepSeekClient
from services.memory_service import render_memory
from storage.json_store import JsonStore

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
store = JsonStore(ROOT / "data" / "girls")

st.set_page_config(page_title="把妹聊天模拟器", page_icon="◌", layout="wide")
st.markdown("""
<style>
:root { --ink:#1f2933; --muted:#687582; --line:#e7ebef; --paper:#fff; --accent:#3a6f68; }
.block-container { max-width: 1080px; padding-top: 2.3rem; padding-bottom: 4rem; }
[data-testid="stSidebar"] { border-right: 1px solid var(--line); }
small, .muted { color: var(--muted); }
[data-testid="stChatMessage"] {
    width: fit-content;
    max-width: 100%;
    border: 1px solid var(--line);
    border-radius: 16px;
    padding: 0.45rem 0.8rem;
}
[class*="st-key-chat-bubble-assistant-"] [data-testid="stChatMessage"] {
    margin-right: auto;
    background: #f3f5f7;
    color: #1f2933;
}
[class*="st-key-chat-bubble-user-"] [data-testid="stChatMessage"] {
    margin-left: auto;
    flex-direction: row-reverse;
    background: #e4f2df;
    color: #1f2933;
}
[class*="st-key-chat-bubble-assistant-"] [data-testid="stChatMessage"] *,
[class*="st-key-chat-bubble-user-"] [data-testid="stChatMessage"] * { color: #1f2933 !important; }
.chat-scroll-button {
    position: fixed;
    right: 1rem;
    z-index: 999;
    display: flex;
    width: 2.25rem;
    height: 2.25rem;
    align-items: center;
    justify-content: center;
    border: 1px solid var(--line);
    border-radius: 50%;
    background: var(--paper);
    color: var(--ink) !important;
    font-size: 1.15rem;
    line-height: 1;
    opacity: 0.62;
    text-decoration: none !important;
    box-shadow: 0 2px 10px #0002;
    transition: opacity 120ms ease, transform 120ms ease;
}
.chat-back-to-top { top: calc(50vh - 2.5rem); }
.chat-back-to-bottom { top: calc(50vh + 0.25rem); }
.chat-scroll-button:hover { opacity: 0.95; transform: translateY(-2px); }
[data-testid="stChatInput"] textarea::placeholder,
[data-testid="stChatInputTextArea"]::placeholder { color: transparent !important; }
button[kind="primary"] { background: var(--accent); border-color: var(--accent); }
</style>
""", unsafe_allow_html=True)

if "page" not in st.session_state:
    st.session_state.page = "home"
if "girl_id" not in st.session_state:
    st.session_state.girl_id = None

with st.sidebar:
    st.markdown("### 把妹聊天模拟器")
    st.caption("练习真诚、平等、尊重边界的交流")
    if st.session_state.girl_id and st.button("当前人物档案", use_container_width=True):
        st.session_state.page = "profile"
        st.rerun()
    st.divider()
    with st.expander("API 设置"):
        env_api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()

        try:
            saved_api_key = get_saved_api_key()
            credential_store_error = None
        except CredentialStoreError as exc:
            saved_api_key = None
            credential_store_error = str(exc)

        api_key = saved_api_key or ""
        if credential_store_error:
            st.error(credential_store_error)

        if saved_api_key:
            st.caption("DeepSeek API Key 已保存在本机 Windows 凭据管理器。")
            with st.expander("更换或删除已保存的 API Key"):
                with st.form("replace_deepseek_api_key", clear_on_submit=True):
                    replacement_api_key = st.text_input("新的 DeepSeek API Key", type="password")
                    replace_key = st.form_submit_button("保存新 Key")
                if replace_key:
                    if not replacement_api_key.strip():
                        st.error("请先输入新的 API Key。")
                    else:
                        try:
                            save_api_key(replacement_api_key.strip())
                            st.rerun()
                        except CredentialStoreError as exc:
                            st.error(str(exc))
                if st.button("删除已保存的 API Key", key="delete_saved_deepseek_api_key"):
                    try:
                        delete_saved_api_key()
                        st.rerun()
                    except CredentialStoreError as exc:
                        st.error(str(exc))
        else:
            with st.form("save_deepseek_api_key", clear_on_submit=True):
                manual_api_key = st.text_input(
                    "输入 DeepSeek API Key",
                    type="password",
                    help="保存后会记在本机 Windows 凭据管理器，下次打开无需重输。",
                )
                save_key = st.form_submit_button("保存到本机")
            if save_key:
                if not manual_api_key.strip():
                    st.error("请先输入 DeepSeek API Key。")
                else:
                    try:
                        save_api_key(manual_api_key.strip())
                        st.rerun()
                    except CredentialStoreError as exc:
                        st.error(str(exc))

            use_environment_key = False
            if env_api_key:
                use_environment_key = st.checkbox(
                    "临时使用本机 DEEPSEEK_API_KEY（Codex 环境变量）",
                    value=False,
                    key="use_environment_deepseek_api_key",
                )
                if use_environment_key:
                    api_key = env_api_key

        st.caption("接口：DeepSeek API · 模型 deepseek-chat。应用无法识别密钥所属账号。")
        if env_api_key and not saved_api_key:
            st.caption("检测到 Windows 环境变量密钥；默认不使用，需临时勾选才会调用。")


def ai_client():
    return DeepSeekClient(api_key)


def navigate(page: str, girl_id: str | None = None):
    st.session_state.page = page
    if girl_id is not None:
        st.session_state.girl_id = girl_id


def profile_summary(girl):
    p = girl["profile"]
    return f"{p['age']} 岁 · {p['city']} · {p['occupation']}"


def format_beijing_time(value):
    if not value:
        return "时间未知"
    try:
        timestamp = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        beijing_time = timestamp.astimezone(timezone(timedelta(hours=8), "北京时间"))
        return beijing_time.strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return str(value)


def render_home():
    st.title("把妹聊天模拟器")
    st.write("认识有自己生活与边界的人，在真实的对话里练习倾听、表达和理解。")
    left, right = st.columns([1, 1])
    with left:
        with st.expander("按描述认识一个人", expanded=True):
            description = st.text_area("简单描述你想认识的人", placeholder="例如：在杭州工作的 24 岁插画师，安静慢热，熟悉后比较幽默。她有自己的生活，不会刻意迎合别人。", height=110)
            if st.button("生成角色", type="primary", key="custom_create"):
                try:
                    with st.spinner("正在构造一个真实、完整的人物…"):
                        profile, affection = CharacterService(ai_client()).create_from_description(description)
                        girl = store.create_girl(profile, affection)
                    st.success(f"已认识 {profile['name']}。")
                    navigate("chat", girl["id"])
                    st.rerun()
                except (AIServiceError, ValueError) as exc:
                    st.error(str(exc))
    with right:
        st.markdown("#### 随机认识一个人")
        st.write("从不同城市、职业、生活阶段与性格中，随机遇见一位成年女性。")
        if st.button("随机认识一个人", type="primary", key="random_create"):
            try:
                with st.spinner("正在安排一次新的相遇…"):
                    profile, affection = CharacterService(ai_client()).create_random()
                    girl = store.create_girl(profile, affection)
                navigate("chat", girl["id"])
                st.rerun()
            except (AIServiceError, ValueError) as exc:
                st.error(str(exc))
    st.divider()
    girls = store.list_girls()
    if store.load_errors:
        with st.expander(f"有 {len(store.load_errors)} 个档案无法读取"):
            for error in store.load_errors:
                st.warning(error)
    query = st.text_input("搜索人物", placeholder="姓名、城市或职业")
    active = [g for g in girls if g.get("status") == "active" and not g.get("archived")]
    history = [g for g in girls if g not in active]
    if query.strip():
        needle = query.strip().casefold()
        matches = lambda g: needle in " ".join(str(v) for v in [g["profile"].get("name"), g["profile"].get("city"), g["profile"].get("occupation")]).casefold()
        active = [g for g in active if matches(g)]
        history = [g for g in history if matches(g)]
    st.subheader("正在认识")
    if not active:
        st.info("这里还没有正在进行的关系。你可以从上方创建一位新人物。")
    for girl in active:
        p = girl["profile"]
        with st.container(border=True):
            a, b = st.columns([4, 1])
            with a:
                st.markdown(f"### {p['name']} · {profile_summary(girl)}")
                st.write(p["personality"])
                st.caption(f"好感度 {girl['affection']:.1f}/10　·　{p['first_impression']}")
            with b:
                if st.button("继续聊天", key=f"chat_{girl['id']}", type="primary", use_container_width=True):
                    navigate("chat", girl["id"])
                    st.rerun()
                if st.button("查看档案", key=f"profile_{girl['id']}", use_container_width=True):
                    navigate("profile", girl["id"])
                    st.rerun()
    with st.expander(f"历史关系与已归档人物（{len(history)}）"):
        if not history:
            st.caption("尚无结束或归档的人物。")
        for girl in history:
            p = girl["profile"]
            status = "已归档" if girl.get("archived") else {"eliminated": "关系自然结束", "ended": "已结束关系"}.get(girl.get("status"), girl.get("status"))
            c, d = st.columns([5, 1])
            c.write(f"**{p['name']}** · {profile_summary(girl)} · {status} · 好感度 {girl['affection']:.1f}")
            if d.button("查看记录", key=f"past_{girl['id']}"):
                navigate("profile", girl["id"])
                st.rerun()


def render_chat_bubble(role, content, index):
    if role == "assistant":
        bubble_column, _ = st.columns([4, 1])
    else:
        _, bubble_column = st.columns([1, 4])
    with bubble_column:
        with st.container(key=f"chat-bubble-{role}-{index}"):
            with st.chat_message(role):
                st.write(content)


def render_chat(girl):
    p = girl["profile"]
    st.markdown(
        '<div id="chat-page-top"></div>'
        '<a class="chat-scroll-button chat-back-to-top" href="#chat-page-top" aria-label="回到顶部" title="回到顶部">↑</a>',
        unsafe_allow_html=True,
    )
    head, profile_action, back_action = st.columns([4, 1.5, 1.2])
    with head:
        st.title(p["name"])
        st.caption(f"{profile_summary(girl)}　·　好感度 {girl['affection']:.1f}/10")
    with profile_action:
        if st.button("查看档案与复盘", key=f"chat_profile_{girl['id']}", width="stretch"):
            navigate("profile", girl["id"])
            st.rerun()
    with back_action:
        if st.button("返回人物列表", width="stretch"):
            navigate("home")
            st.rerun()
    if girl.get("status") != "active":
        st.info("这段关系已经结束。以下历史消息仍可查看。")
    for index, message in enumerate(girl.get("messages", [])):
        role = "assistant" if message.get("role") == "assistant" else "user"
        render_chat_bubble(role, message.get("content", ""), index)
    if girl.get("status") == "active":
        submitted_message_slot = st.empty()
        with st.container():
            content = st.chat_input(
                "输入消息",
                key=f"chat_input_{girl['id']}",
            )
        if content:
            try:
                conversation = ConversationService(store, ai_client())
                user_message = conversation.save_user_message(girl["id"], content)
                with submitted_message_slot.container():
                    render_chat_bubble("user", user_message["content"], len(girl.get("messages", [])))
                    with st.spinner(f"{p['name']} 正在回复…"):
                        conversation.reply_to_latest_user_message(girl["id"])
                st.rerun()
            except (AIServiceError, ValueError) as exc:
                st.error(str(exc))
        with st.container(border=True):
            st.markdown("**聊天辅助**")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("让 AI 帮我找话题（好感度 -1）", key=f"suggest_topic_{girl['id']}", width="stretch"):
                    try:
                        suggestion = ConversationService(store, ai_client()).suggest_topic(girl["id"])
                        st.session_state[f"topic_suggestion_{girl['id']}"] = suggestion
                        st.rerun()
                    except (AIServiceError, ValueError) as exc:
                        st.error(f"{exc} 本次话题请求的好感度扣分仍已生效。")
            with col2:
                if st.button("结束聊天并复盘", key=f"end_chat_{girl['id']}", width="stretch"):
                    try:
                        with st.spinner("正在整理本次互动…"):
                            review = ConversationService(store, ai_client()).end_chat_and_review(girl["id"])
                        st.session_state.recent_review = review
                        navigate("profile", girl["id"])
                        st.rerun()
                    except (AIServiceError, ValueError) as exc:
                        st.error(str(exc))
            topic_suggestion = st.session_state.get(f"topic_suggestion_{girl['id']}")
            if topic_suggestion:
                st.info(f"话题建议（仅供参考，不会自动发送）：{topic_suggestion}")
    st.markdown(
        '<div id="chat-page-bottom"></div>'
        '<a class="chat-scroll-button chat-back-to-bottom" href="#chat-page-bottom" aria-label="回到底部" title="回到底部">↓</a>',
        unsafe_allow_html=True,
    )


def render_profile(girl):
    p = girl["profile"]
    top, back = st.columns([4, 1])
    top.title(p["name"])
    if back.button("返回列表"):
        navigate("home")
        st.rerun()
    st.caption(f"{profile_summary(girl)}　·　好感度 {girl['affection']:.1f}/10　·　状态：{girl['status']}{' · 已归档' if girl.get('archived') else ''}")
    if girl.get("status") == "active":
        c1, c2 = st.columns(2)
        if c1.button("继续聊天", type="primary"):
            navigate("chat", girl["id"])
            st.rerun()
        if c2.button("结束这段关系", help="保留人物、消息和复盘，仅结束后续互动"):
            store.update(girl["id"], lambda item: item.update(status="ended"))
            st.rerun()
    if not girl.get("archived"):
        if st.button("归档人物", help="归档与关系是否结束相互独立，可随时从历史区域查看"):
            store.update(girl["id"], lambda item: item.update(archived=True))
            st.rerun()
    else:
        if st.button("取消归档"):
            store.update(girl["id"], lambda item: item.update(archived=False))
            st.rerun()
    with st.expander("人物完整档案", expanded=True):
        labels = {"background": "成长背景", "personality": "性格", "interests": "兴趣", "communication_style": "交流风格", "values": "价值观", "boundaries": "个人边界", "current_life": "当前生活", "first_impression": "初始印象"}
        st.write(f"**姓名：** {p['name']}　 **年龄：** {p['age']}　 **城市：** {p['city']}　 **职业：** {p['occupation']}")
        for key, label in labels.items():
            value = "、".join(p[key]) if isinstance(p[key], list) else p[key]
            st.write(f"**{label}：** {value}")
    st.subheader("长期关系记忆")
    st.write(render_memory(girl.get("relationship_memory")) or "暂时没有需要长期记住的信息。")
    with st.expander(f"完整聊天记录（{len(girl.get('messages', []))} 条）"):
        for message in girl.get("messages", []):
            who = "你" if message.get("role") == "user" else p["name"]
            st.markdown(f"**{who}** · 北京时间 {format_beijing_time(message.get('created_at'))}")
            st.write(message.get("content", ""))
    st.subheader("历次复盘")
    reviews = list(reversed(girl.get("reviews", [])))
    if not reviews:
        st.caption("还没有复盘记录。")
    for index, review in enumerate(reviews, 1):
        with st.expander(f"复盘 {len(reviews) - index + 1} · 好感度 {review['affection_before']:.1f} → {review['affection_after']:.1f}", expanded=(index == 1)):
            st.markdown("**互动概况**")
            st.write(review["summary"])
            st.markdown("**做得不错的地方**")
            for item in review["strengths"]:
                st.write(f"- {item.get('evidence', '')}　{item.get('reason', '')}" if isinstance(item, dict) else f"- {item}")
            st.markdown("**可以改进的地方**")
            for item in review["improvements"]:
                if isinstance(item, dict):
                    st.write(f"- 具体表达：{item.get('evidence', '')}\n  影响：{item.get('reason', '')}\n  可以试试：{item.get('alternative', '')}")
                else:
                    st.write(f"- {item}")
            st.write(f"**关系变化：** {review['relationship_change']}")
            st.write(f"**好感度变化依据：** {review['reason']}（{review['affection_delta']:+.1f}）")
            st.write(f"**长期记忆：** {review['memory'] or '无新增'}")
    with st.expander("好感度与关系事件"):
        events = list(reversed(girl.get("events", [])))
        if not events:
            st.caption("暂无变化记录。")
        for event in events:
            st.write(f"{event.get('type')} · {event.get('before')} → {event.get('after')} · {event.get('reason')}")


if st.session_state.page == "home":
    render_home()
else:
    current = None
    if st.session_state.girl_id:
        try:
            current = store.get_girl(st.session_state.girl_id)
        except (KeyError, ValueError):
            st.session_state.page = "home"
    if current is None:
        render_home()
    elif st.session_state.page == "chat":
        render_chat(current)
    else:
        render_profile(current)
