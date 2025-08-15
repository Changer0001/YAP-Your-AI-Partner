import streamlit as st
import requests, re, json
from textwrap import dedent

st.set_page_config(page_title="YAP", page_icon="🤖", layout="centered")
API_URL = "http://localhost:8000"


# ── Styles ───────────────────────────────────────────────────────




def inject_styles():
    st.markdown(dedent("""<style>
/* your full CSS (no leading spaces) */
.brand-wrap { max-width:960px; margin:0 auto 1rem; }
.brand-frame { padding:2px; border-radius:18px; background:linear-gradient(135deg,rgba(56,189,248,.55),rgba(168,85,247,.45)); box-shadow:0 18px 42px rgba(56,189,248,.12); }
.brand-inner { border-radius:16px; padding:18px 22px; background:linear-gradient(135deg,rgba(9,15,27,.96),rgba(11,18,32,.96)); border:1px solid rgba(125,211,252,.22); backdrop-filter:blur(6px); -webkit-backdrop-filter:blur(6px); }
.brand-text { font-family:Orbitron, sans-serif; font-size:2.1rem; letter-spacing:.6px; background:linear-gradient(90deg,#7dd3fc,#c4b5fd); -webkit-background-clip:text; background-clip:text; color:transparent; text-shadow:0 0 18px rgba(125,211,252,.15); }

[data-testid="stChatMessageAvatar"]{display:none!important}
.bubble{max-width:860px;margin:.5rem auto 1rem;border-radius:16px}
.user-wrap{background:linear-gradient(135deg,#0b1628 0%,#0a1220 100%);border:1px solid rgba(148,163,184,.14);box-shadow:inset 0 8px 24px rgba(2,8,23,.35),0 6px 18px rgba(0,0,0,.20);padding:.9rem 1rem;border-radius:14px}
.ai-outer{padding:1px;background:linear-gradient(135deg,rgba(56,189,248,.55),rgba(168,85,247,.45));border-radius:16px;box-shadow:0 16px 40px rgba(56,189,248,.16)}
.ai-inner{background:linear-gradient(135deg,rgba(9,15,27,.96),rgba(11,18,32,.96));border:1px solid rgba(125,211,252,.22);border-radius:15px;padding:.95rem 1.1rem;backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px)}
.bubble-title{font-size:.8rem;font-weight:700;letter-spacing:.2px;opacity:.9;margin-bottom:.35rem}
.bubble-title.user{color:#93c5fd}.bubble-title.ai{color:#c4b5fd}
.answer ol{margin-left:1.25em;line-height:1.7em;padding-left:.25em}
.answer p{margin:0 0 .55rem 0}.answer li{margin:.2rem 0}
</style>"""), unsafe_allow_html=True)




# ── Formatting ───────────────────────────────────────────────────
def format_answer(text: str) -> str:
    t = (text or "").strip()
    # newlines before 1. 2. etc
    t = re.sub(r"(?<!\n)(\d+\.)", r"\n\1", t)
    # convert numbered lines to <li>
    t = re.sub(r"(?m)^\s*(\d+)\.\s*(.*)", r"<li>\2</li>", t)
    if "<li>" in t:
        t = f"<ol>{t}</ol>"
    return f"<div class='answer' style='font-size:1.05rem; line-height:1.75em; color:#e2e8f0'>{t}</div>"


def _headline(text: str, max_len: int = 60) -> str:
    t = (text or "").strip()
    t = re.split(r'[\n\.!?]', t)[0]  # first sentence/line
    return (t[:max_len] + "…") if len(t) > max_len else t


# ── State ───────────────────────────────────────────────────────
st.session_state.setdefault("token", None)
st.session_state.setdefault("mode", "login")
st.session_state.setdefault("history", [])  # [{"role":"user"|"assistant","content": "..."}]


# ── Auth ────────────────────────────────────────────────────────
def login(username, password):
    try:
        r = requests.post(f"{API_URL}/login", json={"username": username, "password": password})
        if r.status_code == 401:
            st.error("❌ Invalid credentials.")
            return
        r.raise_for_status()
        token = r.json().get("access_token") or r.json().get("token")
        if not token:
            st.error("Login succeeded but no token returned.")
            return
        st.session_state.token = token
        st.session_state.history = []          # optional: clear any old chat
        st.rerun()                             # <<< key: proceed on first click
    except Exception as e:
        st.error(f"Error: {e}")



def register(username, password):
    try:
        r = requests.post(f"{API_URL}/register", json={"username": username, "password": password})
        if r.status_code == 400: st.error("❌ Username already exists."); return
        r.raise_for_status()
        st.success("✅ Registration successful. Please log in.")
        st.session_state.mode = "login"
    except Exception as e:
        st.error(f"Error: {e}")


# ── Streaming (SSE; no sources) ─────────────────────────────────
def stream_answer(prompt, history, target_placeholder):
    payload = {"question": prompt, "history": history}
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    answer = ""
    try:
        with requests.post(f"{API_URL}/ask/stream", json=payload, headers=headers, stream=True, timeout=(10, 120)) as resp:
            resp.raise_for_status()
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw: 
                    continue
                if raw.startswith(":") or raw.startswith("retry:"):
                    continue
                if raw.startswith("event:"):
                    # ignore custom event types
                    continue
                if raw.startswith("data:"):
                    data_str = raw.split("data:", 1)[1].strip()
                    if not data_str or data_str in ("[DONE]", "{}"):
                        continue
                    try:
                        payload_obj = json.loads(data_str)
                        delta = payload_obj.get("choices", [{}])[0].get("delta", {})
                        piece = delta.get("content", "")
                        if piece:
                            answer += piece
                            target_placeholder.markdown(format_answer(answer), unsafe_allow_html=True)
                    except Exception:
                        continue
                if raw.strip() in ("event: done", "data: [DONE]"):
                    break
    except Exception as e:
        target_placeholder.markdown(f"❌ Stream error: {e}")
        return "[ERROR]"
    return answer.strip()


# ── Pages ───────────────────────────────────────────────────────
def login_page():
    inject_styles()
    # Glassy brand header
    st.markdown(
        "<div class='brand-wrap'><div class='brand-frame'><div class='brand-inner'>"
        "<div class='brand-text'>YAP</div>"
        "</div></div></div>",
        unsafe_allow_html=True,
    )
    st.caption("Sign in to start chatting.")
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            login(u, p)
    if st.button("Create an account"):
        st.session_state.mode = "register"
        st.rerun()


def register_page():
    inject_styles()
    st.markdown(
        "<div class='brand-wrap'><div class='brand-frame'><div class='brand-inner'>"
        "<div class='brand-text'>YAP</div>"
        "</div></div></div>",
        unsafe_allow_html=True,
    )
    with st.form("register_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Register"):
            register(u, p)
    if st.button("Back to Login"):
        st.session_state.mode = "login"
        st.rerun()


def ask_page():
    inject_styles()

    # Brand + subtle subtext
    st.markdown(
        "<div class='brand-wrap'><div class='brand-frame'><div class='brand-inner'>"
        "<div class='brand-text'>YAP</div>"
        "</div></div></div>",
        unsafe_allow_html=True,
    )
    st.caption("Smarter conversations for your business")
    st.divider()

    # Sidebar: actions + chat history headlines
    with st.sidebar:
        st.markdown("## 🧭 Menu")
        if st.button("🗑 Clear chat", key="clear_sidebar", use_container_width=True):
            st.session_state.history = []
            st.rerun()
        if st.button("🚪 Log out", key="logout_sidebar", use_container_width=True):
            st.session_state.token = None
            st.session_state.mode = "login"
            st.rerun()

        st.markdown("---")
        st.markdown("### 📜 Chat history")
        if not st.session_state.history:
            st.caption("No conversation yet.")
        else:
            for i in range(0, len(st.session_state.history), 2):
                try:
                    user_msg = st.session_state.history[i]["content"]
                except Exception:
                    continue
                st.markdown(f"- **{_headline(user_msg)}**")

    # Render existing chat
    for msg in st.session_state.history:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                st.markdown(
                    f"<div class='bubble ai-outer'><div class='ai-inner'>"
                    f"<div class='bubble-title ai'>YAP</div>"
                    f"{format_answer(msg['content'])}"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div class='bubble user-wrap'>"
                    f"<div class='bubble-title user'>You</div>"
                    f"{msg['content']}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # Composer (Enter to send)
    prompt = st.chat_input("Ask your question…")
    if prompt:
        # render user message immediately
        st.session_state.history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(
                f"<div class='bubble user-wrap'><div class='bubble-title user'>You</div>{prompt}</div>",
                unsafe_allow_html=True,
            )
        # assistant streaming
        with st.chat_message("assistant"):
            st.markdown(
                "<div class='bubble ai-outer typing'><div class='ai-inner'>"
                "<div class='bubble-title ai'>YAP</div><div id='stream'></div>"
                "</div></div>",
                unsafe_allow_html=True,
            )
            ph = st.empty()
            answer = stream_answer(prompt, st.session_state.history, target_placeholder=ph)
            if answer and not answer.startswith("[ERROR]"):
                st.session_state.history.append({"role": "assistant", "content": answer})


# ── Main ────────────────────────────────────────────────────────
def main():
    if st.session_state.token:
        ask_page()
        st.stop()   # prevents any login UI from rendering after chat
    elif st.session_state.mode == "login":
        login_page()
    else:
        register_page()


main()
