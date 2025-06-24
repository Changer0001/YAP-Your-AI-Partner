import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000"

# --- Session State Defaults ---
if "token" not in st.session_state:
    st.session_state.token = None
if "page" not in st.session_state:
    st.session_state.page = "login"

# --- Login Page ---
def login():
    st.title("🔐 Login")

    username = st.text_input("Username", key="login_username")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login"):
        if not username or not password:
            st.warning("Please enter both username and password.")
            return

        try:
            res = requests.post(f"{API_URL}/login", json={"username": username, "password": password})
            if res.status_code == 200:
                st.session_state.token = res.json()["access_token"]
                st.session_state.page = "ask"
                st.success("✅ Logged in successfully!")
                st.rerun()
            else:
                st.error(res.json().get("detail", "Invalid login."))
        except requests.exceptions.RequestException as e:
            st.error(f"Server error: {e}")

    if st.button("Go to Register"):
        st.session_state.page = "register"
        st.rerun()

# --- Register Page ---
def register():
    st.title("📝 Register")

    username = st.text_input("Choose a username", key="register_username")
    password = st.text_input("Choose a password", type="password", key="register_password")

    if st.button("Register"):
        if not username or not password:
            st.warning("Username and password are required.")
            return

        try:
            res = requests.post(f"{API_URL}/register", json={"username": username, "password": password})
            if res.status_code == 200:
                st.success("✅ Registered successfully! Please log in.")
                st.session_state.page = "login"
                st.rerun()
            else:
                st.error(res.json().get("detail", "Registration failed."))
        except requests.exceptions.RequestException as e:
            st.error(f"Server error: {e}")

    if st.button("Go to Login"):
        st.session_state.page = "login"
        st.rerun()

# --- Ask Page ---
def ask_page():
    st.title("📚 LLM Assistance - Ask a Question")

    if not st.session_state.token:
        st.warning("⚠️ You must be logged in.")
        st.session_state.page = "login"
        st.rerun()
        return

    with st.form("ask_form"):
        question = st.text_input("❓ Enter your question", key="question_input")
        submitted = st.form_submit_button("Get Answer")

    if submitted:
        if not question.strip():
            st.warning("Please enter a question.")
            return

        headers = {"Authorization": f"Bearer {st.session_state.token}"}

        try:
            res = requests.post(f"{API_URL}/ask", json={"question": question}, headers=headers)
            if res.status_code == 200:
                answer = res.json()["answer"]
                st.markdown(f"**✅ Answer:**\n\n{answer}")
            else:
                st.error(f"{res.status_code}: {res.json().get('detail', '❌ Failed to get answer.')}")
        except requests.exceptions.RequestException as e:
            st.error(f"Connection error: {e}")

    # --- Chat History Display ---
    if st.button("🕓 Show Chat History"):
        headers = {"Authorization": f"Bearer {st.session_state.token}"}
        try:
            res = requests.get(f"{API_URL}/history", headers=headers)
            if res.status_code == 200:
                history = res.json()
                if history:
                    st.subheader("📜 Chat History")
                    for entry in history:
                        st.markdown(f"**🧑 You:** {entry['question']}")
                        st.markdown(f"**🤖 Assistant:** {entry['answer']}")
                        timestamp = entry.get("timestamp", None)
                        if timestamp:
                            st.caption(f"🕒 {timestamp}")
                        st.markdown("---")
                else:
                    st.info("No chat history yet.")
            else:
                st.warning("Failed to retrieve history.")
        except requests.exceptions.RequestException as e:
            st.error(f"Error fetching history: {e}")

    if st.button("Logout"):
        st.session_state.token = None
        st.session_state.page = "login"
        st.rerun()

# --- Page Router ---
def render():
    page = st.session_state.get("page", "login")
    if page == "login":
        login()
    elif page == "register":
        register()
    elif page == "ask":
        ask_page()
    else:
        st.error("🚨 Unknown page.")

render()
