import streamlit as st
import requests
import time

API_URL = "http://127.0.0.1:8000"

# --- Session State ---
st.session_state.setdefault("token", None)
st.session_state.setdefault("page", "login")
st.session_state.setdefault("question_input", "")
st.session_state.setdefault("history", [])

# --- Stream Answer from Backend ---
def stream_answer(question):
    headers = headers = {"token": st.session_state.token}

    placeholder = st.empty()

    def generate():
        with requests.post(
            f"{API_URL}/ask/stream",
            json={"question": question},
            headers=headers,
            stream=True,
        ) as res:
            try:
                res.raise_for_status()
            except requests.HTTPError:
                st.error(f"❌ {res.status_code} - {res.text}")
                raise
            for chunk in res.iter_lines():
                if chunk:
                    yield chunk.decode("utf-8")

    with st.spinner("🤖 Thinking..."):
        start = time.time()
        full_answer = ""
        for chunk in generate():
            for char in chunk:
                full_answer += char
                placeholder.markdown(f"**✅ Answer:**\n\n{full_answer}")
                time.sleep(0.008)  # Typing effect

        duration = time.time() - start
        st.caption(f"⏱️ Answered in {duration:.2f} seconds")
        return full_answer

# --- Login ---
def login():
    st.title("🔐 Login")
    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login"):
        if not username or not password:
            st.warning("Please enter both fields.")
            return
        try:
            res = requests.post(f"{API_URL}/login", json={"username": username, "password": password})
            if res.status_code == 200:
                st.session_state.token = res.json()["access_token"]
                st.session_state.page = "ask"
                st.rerun()
            else:
                st.error(res.json().get("detail", "Login failed."))
        except Exception as e:
            st.error(f"Connection error: {e}")

    if st.button("Go to Register"):
        st.session_state.page = "register"

# --- Register ---
def register():
    st.title("📝 Register")
    username = st.text_input("Choose a username", key="register_username")
    password = st.text_input("Choose a password", type="password", key="register_password")

    if st.button("Register"):
        if not username or not password:
            st.warning("Username and password required.")
            return
        try:
            res = requests.post(f"{API_URL}/register", json={"username": username, "password": password})
            if res.status_code == 200:
                st.success("✅ Registered! You can now login.")
                st.session_state.page = "login"
            else:
                st.error(res.json().get("detail", "Registration failed."))
        except Exception as e:
            st.error(f"Connection error: {e}")

    if st.button("Go to Login"):
        st.session_state.page = "login"

# --- Ask Page ---
def ask_page():
    st.title("📚 LLM Assistant - Ask Anything")

    if not st.session_state.token:
        st.warning("⚠️ Please log in.")
        st.session_state.page = "login"
        return

    question = st.text_input("❓ Enter your question", key="question_input")

    if st.button("Get Answer"):
        question = st.session_state.question_input.strip()
        if not question:
            st.warning("Please enter a question.")
            return

        response = stream_answer(question)
        if response:
            st.session_state.history.append({
                "question": question,
                "answer": response,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            })

    if st.button("🕓 Show Chat History"):
        show_history()

    if st.button("Logout"):
        st.session_state.token = None
        st.session_state.page = "login"

# --- History Display ---
def show_history():
    st.subheader("📜 Chat History")
    headers = {"Authorization": f"Bearer {st.session_state.token}"}
    try:
        res = requests.get(f"{API_URL}/history", headers=headers)
        if res.status_code == 200:
            history_data = res.json()
            if not history_data:
                st.info("No history yet.")
                return
            for entry in reversed(history_data):
                st.markdown(f"**🧑 You:** {entry['question']}")
                st.markdown(f"**🤖 Assistant:** {entry['answer']}")
                st.caption(f"🕒 {entry['timestamp']}")
                st.markdown("---")
        else:
            st.error("Failed to fetch history.")
    except Exception as e:
        st.error(f"Connection error: {e}")

# --- Page Router ---
def render():
    if st.session_state.page == "login":
        login()
    elif st.session_state.page == "register":
        register()
    elif st.session_state.page == "ask":
        ask_page()
    else:
        st.error("🚨 Unknown page.")

render()
