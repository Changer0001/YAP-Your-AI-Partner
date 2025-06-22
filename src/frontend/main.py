import streamlit as st
import requests

API_URL = "http://localhost:8000"

# Initialize session state
if "token" not in st.session_state:
    st.session_state.token = None
if "page" not in st.session_state:
    st.session_state.page = "login"

# --- Auth Pages ---
def login():
    st.title("🔐 Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        res = requests.post(f"{API_URL}/login", json={"username": username, "password": password})
        if res.status_code == 200:
            st.session_state.token = res.json()["access_token"]
            st.session_state.page = "ask"
            st.success("Logged in successfully!")
        else:
            st.error("Invalid username or password")

    st.button("Go to Register", on_click=lambda: st.session_state.update({"page": "register"}))

def register():
    st.title("📝 Register")
    username = st.text_input("Choose a username")
    password = st.text_input("Choose a password", type="password")
    if st.button("Register"):
        res = requests.post(f"{API_URL}/register", json={"username": username, "password": password})
        if res.status_code == 200:
            st.success("Registered successfully! Please log in.")
            st.session_state.page = "login"
        else:
            st.error(res.json()["detail"])

    st.button("Go to Login", on_click=lambda: st.session_state.update({"page": "login"}))

# --- Main Ask Page ---
def ask_page():
    st.title("📚 LLM Assistance - Ask a Question")

    question = st.text_input("❓ Enter your question")
    if st.button("Get Answer"):
        if not question.strip():
            st.warning("Please enter a question.")
        else:
            headers = {"Authorization": f"Bearer {st.session_state.token}"}
            res = requests.post(f"{API_URL}/ask", json={"question": question}, headers=headers)
            if res.status_code == 200:
                data = res.json()
                st.markdown(f"**Answer:** {data['answer']}")
            else:
                st.error(res.json().get("detail", "Failed to get answer"))

    st.button("Logout", on_click=lambda: st.session_state.update({"token": None, "page": "login"}))

# --- Page Routing ---
if st.session_state.page == "login":
    login()
elif st.session_state.page == "register":
    register()
else:
    ask_page()
