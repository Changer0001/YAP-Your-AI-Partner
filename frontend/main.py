import streamlit as st
import requests, re, json
from streamlit.components.v1 import html as html_component

st.set_page_config(page_title="YAP • Your AI Partner", page_icon="🤖", layout="centered")
API_URL = "http://localhost:8000"

# ── Styles ───────────────────────────────────────────────────────
def inject_styles():
    st.markdown(
        """
    ...
    <style>
        html, body, [class*="css"] { ... }
        .stApp { ... }
        h1 { ... }
        input, textarea { ... }
        .stButton>button { ... }

        /* ▼ replace ONLY these two rules ▼ */
        .chat-bubble {
            background: linear-gradient(135deg, #0b1628 0%, #0a1220 100%);
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 14px;
            border: 1px solid rgba(148, 163, 184, 0.14);
            box-shadow: inset 0 8px 24px rgba(2, 8, 23, 0.35),
                        0 6px 18px rgba(0, 0, 0, 0.20);
        }
        .ai-bubble {
            background: radial-gradient(120% 120% at 0% 0%,
                        rgba(56, 189, 248, 0.10),
                        rgba(99, 102, 241, 0.10) 40%,
                        #0b1220 100%);
            border: 1px solid rgba(56, 189, 248, 0.28);
            box-shadow: 0 12px 28px rgba(56, 189, 248, 0.14),
                        inset 0 2px 0 rgba(56, 189, 248, 0.06);
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 14px;
        }
        /* ▲ replace ONLY these two rules ▲ */
        /* --- bubble overrides (v2) --- */
        .chat-bubble {
        background: linear-gradient(135deg, #0b1628 0%, #0a1220 100%) !important;
        border: 1px solid rgba(148,163,184,.14) !important;
        box-shadow:
            inset 0 8px 24px rgba(2,8,23,.35),
            0 6px 18px rgba(0,0,0,.20) !important;
        }

        /* make AI bubble visibly cyan/violet + glass */
        .chat-bubble.ai-bubble {
        background:
            radial-gradient(120% 120% at 0% 0%,
            rgba(56,189,248,.28),
            rgba(99,102,241,.22) 40%,
            rgba(11,18,32,1) 100%) !important;
        border: 1px solid rgba(56,189,248,.38) !important;
        box-shadow:
            0 14px 34px rgba(56,189,248,.24),
            inset 0 2px 0 rgba(255,255,255,.04) !important;
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        }

    </style>
    """,
        unsafe_allow_html=True,
    )



# ── Answer formatter ─────────────────────────────────────────────
def format_answer(text: str) -> str:
    t = (text or "").strip()
    t = re.sub(r"(?<!\n)(\d+\.)", r"\n\1", t)
    t = re.sub(r"(?m)^\s*(\d+)\.\s*(.*)", r"<li>\2</li>", t)
    if "<li>" in t:
        t = f"<ol>{t}</ol>"
    return f"<div class='answer' style='font-size:1.05rem; line-height:1.75em; color:#e2e8f0'>{t}</div>"

# ── State ───────────────────────────────────────────────────────
st.session_state.setdefault("token", None)
st.session_state.setdefault("mode", "login")
st.session_state.setdefault("history", [])  # [{"role":"user"|"assistant","content": "..."}]

# ── Auth ────────────────────────────────────────────────────────
def login(username, password):
    try:
        r = requests.post(f"{API_URL}/login", json={"username": username, "password": password})
        if r.status_code == 401: st.error("❌ Invalid credentials."); return
        r.raise_for_status(); st.session_state.token = r.json().get("access_token"); st.success("✅ Logged in.")
    except Exception as e: st.error(f"Error: {e}")

def register(username, password):
    try:
        r = requests.post(f"{API_URL}/register", json={"username": username, "password": password})
        if r.status_code == 400: st.error("❌ Username already exists."); return
        r.raise_for_status(); st.success("✅ Registration successful. Please log in."); st.session_state.mode = "login"
    except Exception as e: st.error(f"Error: {e}")

# ── Streaming (SSE; no Sources) ─────────────────────────────────
def stream_answer(prompt, history, target_placeholder):
    payload = {"question": prompt, "history": history}
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    answer = ""; event_type = None
    try:
        with requests.post(f"{API_URL}/ask/stream", json=payload, headers=headers, stream=True, timeout=(10, 120)) as resp:
            resp.raise_for_status()
            for raw in resp.iter_lines(decode_unicode=True):
                if not raw: continue
                if raw.startswith(":") or raw.startswith("retry:"): continue
                if raw.startswith("event:"):
                    event_type = raw.split("event:", 1)[1].strip(); continue
                if raw.startswith("data:"):
                    data_str = raw.split("data:", 1)[1].strip()
                    if not data_str or data_str in ("[DONE]", "{}"): continue
                    try:
                        payload_obj = json.loads(data_str)
                        delta = payload_obj.get("choices", [{}])[0].get("delta", {})
                        piece = delta.get("content", "")
                        if piece:
                            answer += piece
                            target_placeholder.markdown(format_answer(answer), unsafe_allow_html=True)
                    except Exception:
                        continue
                if raw.strip() in ("event: done", "data: [DONE]"): break
    except Exception as e:
        target_placeholder.markdown(f"❌ Stream error: {e}")
        return "[ERROR]"
    return answer.strip()

# ── Pages ───────────────────────────────────────────────────────
def login_page():
    inject_styles()
    st.title("🤖 YAP: Your AI Partner")
    st.caption("Sign in to start chatting.")
    with st.form("login_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Login"): login(u, p)
    if st.button("Create an account"): st.session_state.mode = "register"; st.rerun()

def register_page():
    inject_styles()
    st.title("Create your YAP account")
    with st.form("register_form"):
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")
        if st.form_submit_button("Register"): register(u, p)
    if st.button("Back to Login"): st.session_state.mode = "login"; st.rerun()

def ask_page():
    inject_styles()
    st.title("🤖 YAP: Your AI Partner")
    st.caption("Smarter conversations for your business")
    st.divider()

    # Top-right toolbar
    a, b, c = st.columns([1, 0.12, 0.12], vertical_alignment="center")
    with b:
        if st.button("🗑 Clear", key="clear", help="Clear chat history"):
            st.session_state.history = []; st.rerun()
    with c:
        if st.button("🚪 Logout", key="logout", help="Sign out"):
            st.session_state.token = None; st.session_state.mode = "login"; st.rerun()
    st.write("")  # small spacer

    # Render history with custom labels + bubbles
    for msg in st.session_state.history:
        with st.chat_message(msg["role"]):
            if msg["role"] == "assistant":
                st.markdown(
                    f"<div class='bubble ai-outer'><div class='ai-inner'>"
                    f"<span class='label ai'>YAP</span><div style='height:.35rem'></div>{format_answer(msg['content'])}"
                    f"</div></div>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"<div class='bubble user-wrap'>"
                    f"<span class='label user'>You</span><div style='height:.35rem'></div>{msg['content']}"
                    f"</div>",
                    unsafe_allow_html=True,
                )

    # Composer (Enter to send)
    prompt = st.chat_input("Ask your question…")
    if prompt:
        st.session_state.history.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(
                f"<div class='bubble user-wrap'><span class='label user'>You</span><div style='height:.35rem'></div>{prompt}</div>",
                unsafe_allow_html=True,
            )
        with st.chat_message("assistant"):
            st.markdown("<div class='bubble ai-outer typing'><div class='ai-inner'><span class='label ai'>YAP</span><div style='height:.35rem'></div><div id='stream'></div></div></div>", unsafe_allow_html=True)
            ph = st.empty()
            answer = stream_answer(prompt, st.session_state.history, target_placeholder=ph)
            if answer and not answer.startswith("[ERROR]"):
                st.session_state.history.append({"role": "assistant", "content": answer})

# ── Main ────────────────────────────────────────────────────────
def main():
    if st.session_state.token:
        ask_page()
    elif st.session_state.mode == "login":
        login_page()
    else:
        register_page()

main()
