import streamlit as st
import requests
import time
import re
import json

API_URL = "http://localhost:8000"  # 🌐 Update this if deployed

# ── Global Styles ────────────────────────────────────────────────
def inject_styles():
    st.markdown("""
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Orbitron:wght@600&display=swap" rel="stylesheet">
    <style>
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            background-color: #0f172a;
            color: #e2e8f0;
        }
        .stApp {
            padding: 2rem;
        }
        h1 {
            font-family: 'Orbitron', sans-serif;
            color: #38bdf8;
        }
        input, textarea {
            background-color: #1e293b !important;
            color: #e2e8f0 !important;
            border-radius: 8px;
            padding: 8px;
        }
        .stButton>button {
            background-color: #3b82f6 !important;
            color: white !important;
            border-radius: 10px;
            padding: 0.4rem 1.5rem;
            font-weight: 600;
        }
        .chat-bubble {
            background-color: #1e293b;
            padding: 1rem;
            margin-bottom: 1rem;
            border-radius: 12px;
        }
    </style>
    """, unsafe_allow_html=True)

# ── Format Answer ───────────────────────────────────────────────
def format_answer(answer: str) -> str:
    answer = answer.strip()
    answer = re.sub(r"(?<!\n)(\d+\.)", r"\n\1", answer)
    answer = re.sub(r"(?m)^\s*(\d+)\.\s*(.*)", r"<li>\2</li>", answer)

    if "<li>" in answer:
        answer = f"<ol style='margin-left: 1.5em; line-height: 1.7em;'>{answer}</ol>"

    return f"""
    <div style='font-size: 1.05rem; line-height: 1.6em; color: #e2e8f0;'>
        {answer}
    </div>
    """

# ── Session State Init ─────────────────────────────────────────
st.session_state.setdefault("token", None)
st.session_state.setdefault("mode", "login")
st.session_state.setdefault("history", [])
st.session_state.setdefault("last_answer", None)

# ── Authentication ─────────────────────────────────────────────
def login(username, password):
    try:
        res = requests.post(f"{API_URL}/login", json={"username": username, "password": password})
        if res.status_code == 401:
            st.error("❌ Invalid credentials.")
            return
        res.raise_for_status()
        st.session_state.token = res.json().get("access_token")
        st.success("✅ Logged in.")
    except Exception as e:
        st.error(f"Error: {e}")

def register(username, password):
    try:
        res = requests.post(f"{API_URL}/register", json={"username": username, "password": password})
        res.raise_for_status()
        st.success("✅ Registration successful.")
        st.session_state.mode = "login"
    except requests.exceptions.HTTPError as e:
        if res.status_code == 400:
            st.error("❌ Username exists.")
        else:
            st.error(f"❌ Registration failed: {e}")
    except Exception as e:
        st.error(f"❌ {e}")

# ── Streaming Logic ─────────────────────────────────────────────
def stream_answer(prompt, history):
    payload = {"question": prompt, "history": history}
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    answer = ""
    placeholder = st.empty()

    try:
        with requests.post(f"{API_URL}/ask/stream", json=payload, headers=headers, stream=True) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line or line == b"data: [DONE]":
                    continue

                try:
                    # Clean "data: ..." prefix and parse
                    clean = line.decode("utf-8").removeprefix("data: ")
                    payload = json.loads(clean)
                    content_piece = payload.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if content_piece:
                        answer += content_piece
                        placeholder.markdown(format_answer(answer), unsafe_allow_html=True)
                except Exception as e:
                    print(f"⚠️ Failed to parse stream: {e}")
                    continue

    except Exception as e:
        st.error(f"❌ Stream error: {e}")
        return "[ERROR]"
    return answer.strip()

# ── Pages ──────────────────────────────────────────────────────
def login_page():
    inject_styles()
    st.title("🔐 Login to YAP")
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
    st.title("📝 Register for YAP")
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
    st.title("🤖 YAP: Your AI Partner")
    st.caption("Smarter conversations for your business")

    # ── Right-Aligned Input Box with Enter Submit ─────────────
    with st.form("ask_form", clear_on_submit=True):
        cols = st.columns([0.1, 0.1, 0.8])  # adjust spacing if needed
        with cols[2]:  # far right column
            user_input = st.text_input(
                " ", 
                placeholder="Ask your question...",
                label_visibility="collapsed"
            )
        submitted = st.form_submit_button("Send")

    if submitted and user_input.strip():
        question = user_input.strip()
        answer = stream_answer(question, st.session_state.history)
        if answer and not answer.startswith("[ERROR]"):
            st.session_state.history.extend([
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer}
            ])
            st.session_state.last_answer = answer
            st.rerun()

    # ── Show Last Answer ──────────────────────────────────────
    if st.session_state.get("last_answer"):
        st.markdown(format_answer(st.session_state.last_answer), unsafe_allow_html=True)
        st.session_state.last_answer = None

    # ── Chat History ──────────────────────────────────────────
    with st.expander("📜 Chat History"):
        if not st.session_state.history:
            st.info("No conversation yet.")
        for m in reversed(st.session_state.history):
            who = "🧑" if m["role"] == "user" else "🤖"
            st.markdown(f"<div class='chat-bubble'><strong>{who}:</strong> {m['content']}</div>", unsafe_allow_html=True)

    # ── Footer Buttons ────────────────────────────────────────
    cols = st.columns(3)
    if cols[0].button("🗑 Clear"):
        st.session_state.history = []
        st.rerun()
    if cols[1].button("🚪 Logout"):
        st.session_state.token = None
        st.session_state.mode = "login"
        st.rerun()


# ── App Router ─────────────────────────────────────────────────
def main():
    if st.session_state.token:
        ask_page()
    elif st.session_state.mode == "login":
        login_page()
    elif st.session_state.mode == "register":
        register_page()

main()
