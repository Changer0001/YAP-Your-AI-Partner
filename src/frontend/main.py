import streamlit as st
import requests
import time
import re
import json

API_URL = "http://localhost:8000"  # 🧠 Your FastAPI backend

# ── Format Answer ───────────────────────────────────────────────
def format_answer(answer: str) -> str:
    answer = answer.strip()
    answer = re.sub(r"(?m)^\\s*\\d+\\.\\s*", "- ", answer)
    answer = re.sub(r"(?m)^\\s*-\\s*", "<li>", answer)
    answer = re.sub(r"(?m)(<li>.*?)(?=\\n|$)", r"\1</li>", answer)
    if "<li>" in answer:
        answer = f"<ul>{answer}</ul>"
    return f"<p style='font-size: 1rem; line-height: 1.6em;'>{answer}</p>"

# ── Session Setup ───────────────────────────────────────────────
st.session_state.setdefault("token", None)
st.session_state.setdefault("page", "ask")
st.session_state.setdefault("mode", "login")  # 'login' or 'register'
st.session_state.setdefault("question_input", "")
st.session_state.setdefault("history", [])
st.session_state.setdefault("last_answer", None)

# ── Login ───────────────────────────────────────────────────────
def login(username, password):
    try:
        res = requests.post(f"{API_URL}/login", json={
            "username": username,
            "password": password
        })

        # Explicitly handle HTTP errors
        if res.status_code == 401:
            st.error("❌ Invalid username or password.")
            return

        res.raise_for_status()  # raise for other errors (like 500)

        token = res.json().get("access_token")
        if not token:
            st.error("❌ Login failed: No token received.")
            return

        st.session_state.token = token
        st.success("✅ Logged in successfully!")

    except requests.exceptions.HTTPError as e:
        st.error(f"❌ Server error: {e}")
    except Exception as e:
        st.error(f"❌ Unexpected error: {e}")



# ── Stream Answer from `/ask/stream` ────────────────────────────
def stream_answer(prompt: str, history: list) -> str:
    formatted_history = [
        {"role": msg.get("role", ""), "content": msg.get("content", "")}
        for msg in history
        if isinstance(msg, dict)
        and msg.get("role") in {"user", "assistant"}
        and isinstance(msg.get("content"), str)
]

    # ✅ Always send history
    payload = {"question": prompt.strip(), "history": formatted_history}


    try:
        json.dumps(payload)
    except Exception as e:
        st.error(f"❌ Invalid payload: {e}")
        return "[ERROR] Invalid JSON"

    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    answer = ""
    placeholder = st.empty()

    try:
        with requests.post(f"{API_URL}/ask/stream", json=payload, headers=headers, stream=True) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                content = line.decode("utf-8")
                answer += content
                placeholder.markdown(format_answer(answer), unsafe_allow_html=True)
                time.sleep(0.008)
    except Exception as e:
        st.error(f"❌ Failed to get answer: {e}")
        return "[ERROR] Unable to get response."

    return answer.strip()



# ── UI: Login Page ──────────────────────────────────────────────
def login_page():
    st.title("🔐 Login to LLM Assistant")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Login")
        if submit:
            login(username, password)

    st.markdown("Don't have an account?")
    if st.button("Create Account"):
        st.session_state.mode = "register"
        st.rerun()

def register_page():
    st.title("📝 Register New Account")
    with st.form("register_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submit = st.form_submit_button("Register")

        if submit:
            try:
                res = requests.post(f"{API_URL}/register", json={
                    "username": username,
                    "password": password
                })
                res.raise_for_status()
                st.success("✅ Registration successful! You can now log in.")
                time.sleep(1)
                st.session_state.mode = "login"
                st.rerun()
            except requests.exceptions.HTTPError as e:
                if res.status_code == 400:
                    st.error("❌ Username already exists.")
                else:
                    st.error(f"❌ Registration failed: {e}")
            except Exception as e:
                st.error(f"❌ Error: {e}")


# ── UI: Ask Page ────────────────────────────────────────────────
def ask_page():
    st.title("📚 LLM Assistant - Ask Anything")

    question_input = st.text_input("❓ Enter your question", key="question_input")

    # Clean history (remove bad formats and [ERROR] content)
    st.session_state.history = [
        h for h in st.session_state.history
        if (
            isinstance(h, dict)
            and "role" in h
            and "content" in h
            and h["role"] in {"user", "assistant"}
            and not h["content"].startswith("[ERROR]")
        )
    ]

    if st.session_state.get("last_answer"):
        st.markdown(format_answer(st.session_state.last_answer), unsafe_allow_html=True)
        st.session_state.last_answer = None

    # Answer flow
    if st.button("Get Answer"):
        question = question_input.strip()
        if not question:
            st.warning("Please enter a question.")
            return
        
        # Ask
        answer = stream_answer(question, st.session_state.history)

        # Skip error answers
        if answer.startswith("[ERROR]"):
            st.error("⚠️ Skipping error response from history.")
            return

        # Save valid history
        st.session_state.history.extend([
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer}
        ])
        st.session_state.last_answer = answer
        st.rerun()

    # Utility buttons
    if st.button("🕓 Show Chat History"):
        show_history()

    if st.button("🔄 Clear History"):
        st.session_state.history = []
        st.rerun()

    if st.button("🚪 Logout"):
        st.session_state.token = None
        st.session_state.history = []
        st.rerun()



# ── UI: History Viewer ─────────────────────────────────────────
def show_history():
    st.subheader("📜 Chat History")
    if not st.session_state.history:
        st.info("No history yet.")
        return
    for msg in reversed(st.session_state.history):
        prefix = "🧑 You" if msg["role"] == "user" else "🤖 Assistant"
        st.markdown(f"**{prefix}:** {msg['content']}")
        st.markdown("---")

# ── Router ─────────────────────────────────────────────────────
def render():
    if not st.session_state.token:
        if st.session_state.mode == "login":
            login_page()
        elif st.session_state.mode == "register":
            register_page()
    else:
        ask_page()
    if st.button("⬅️ Back to Login"):
        st.session_state.mode = "login"
        st.rerun()
render()
