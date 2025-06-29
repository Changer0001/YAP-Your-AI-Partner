import streamlit as st
import requests
import time

API_URL = "http://127.0.0.1:8000"

# ── Session State ─────────────────────────────────────────────────────────────
st.session_state.setdefault("token", None)
st.session_state.setdefault("page", "login")
st.session_state.setdefault("question_input", "")
st.session_state.setdefault("history", [])    # [{role, content} …]

# ── Helper: Stream answer from backend ────────────────────────────────────────
def stream_answer(payload: dict) -> str:
    headers = {"token": st.session_state.token}
    placeholder = st.empty()

    def generate():
        with requests.post(f"{API_URL}/ask/stream",
                           json=payload,
                           headers=headers,
                           stream=True) as res:
            res.raise_for_status()
            for chunk in res.iter_lines():
                if chunk:
                    yield chunk.decode("utf-8")

    with st.spinner("🤖 Thinking..."):
        start = time.time()
        answer = ""
        for chunk in generate():
            answer += chunk
            placeholder.markdown(f"**✅ Answer:**\n\n{answer}")
            time.sleep(0.008)
        st.caption(f"⏱️ Answered in {time.time() - start:.2f} s")
        return answer

# ── Login / Register views ────────────────────────────────────────────────────
def login():
    st.title("🔐 Login")
    u = st.text_input("Username", key="login_username")
    p = st.text_input("Password", type="password", key="login_password")
    if st.button("Login"):
        if not u or not p:
            st.warning("Please enter both fields.")
            return
        try:
            r = requests.post(f"{API_URL}/login", json={"username": u, "password": p})
            if r.status_code == 200:
                st.session_state.token = r.json()["access_token"]
                st.session_state.page = "ask"
                st.rerun()
            else:
                st.error(r.json().get("detail", "Login failed."))
        except Exception as e:
            st.error(f"Connection error: {e}")
    if st.button("Go to Register"):
        st.session_state.page = "register"

def register():
    st.title("📝 Register")
    u = st.text_input("Choose a username", key="register_username")
    p = st.text_input("Choose a password", type="password", key="register_password")
    if st.button("Register"):
        if not u or not p:
            st.warning("Username and password required.")
            return
        try:
            r = requests.post(f"{API_URL}/register", json={"username": u, "password": p})
            if r.status_code == 200:
                st.success("✅ Registered! You can now login.")
                st.session_state.page = "login"
            else:
                st.error(r.json().get("detail", "Registration failed."))
        except Exception as e:
            st.error(f"Connection error: {e}")
    if st.button("Go to Login"):
        st.session_state.page = "login"

# ── Chat view ─────────────────────────────────────────────────────────────────
def ask_page():
    st.title("📚 LLM Assistant - Ask Anything")

    if not st.session_state.token:
        st.warning("⚠️ Please log in.")
        st.session_state.page = "login"
        return

    question_input = st.text_input("❓ Enter your question", key="question_input")

    # ✅ Show the last answer if it exists
    if st.session_state.get("last_answer"):
        st.markdown(f"**✅ Answer:**\n\n{st.session_state.last_answer}")
        st.session_state.last_answer = None  # Clear after showing

    if st.button("Get Answer"):
        question = question_input.strip()
        if not question:
            st.warning("Please enter a question.")
            return

        payload = {"question": question, "history": st.session_state.history}
        answer = stream_answer(payload)

        if answer:
            st.session_state.history.extend([
                {"role": "user", "content": question},
                {"role": "assistant", "content": answer}
            ])
            st.session_state.last_answer = answer  # ✅ Store answer before rerun
            st.rerun()  # 🔁 trigger rerun to update view

    if st.button("🕓 Show Chat History"):
        show_history()

    if st.button("Logout"):
        st.session_state.token = None
        st.session_state.page = "login"
        st.session_state.history = []
        st.session_state.last_answer = None  # ✅ clear this too
        st.rerun()


# ── Local history viewer ──────────────────────────────────────────────────────
def show_history():
    st.subheader("📜 Chat History (this session)")
    if not st.session_state.history:
        st.info("No history yet.")
        return
    for msg in reversed(st.session_state.history):
        prefix = "🧑 You" if msg["role"] == "user" else "🤖 Assistant"
        st.markdown(f"**{prefix}:** {msg['content']}")
        st.markdown("---")

# ── Page router ───────────────────────────────────────────────────────────────
def render():
    page = st.session_state.page
    if page == "login":
        login()
    elif page == "register":
        register()
    elif page == "ask":
        ask_page()
    else:
        st.error("🚨 Unknown page.")

render()
