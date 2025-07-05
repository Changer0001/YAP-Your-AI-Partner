import streamlit as st
import requests
import time
import re
import json

API_URL = "https://4181-35-247-165-206.ngrok-free.app/v1"  # <-- Replace if Ngrok URL changes

# ── Helper: Format Answer ───────────────────────────────────────────────────
def format_answer(answer: str) -> str:
    answer = answer.strip()
    answer = re.sub(r"(?m)^\\s*\\d+\\.\\s*", "- ", answer)
    answer = re.sub(r"(?m)^\\s*-\\s*", "<li>", answer)
    answer = re.sub(r"(?m)(<li>.*?)(?=\\n|$)", r"\1</li>", answer)
    if "<li>" in answer:
        answer = f"<ul>{answer}</ul>"
    return f"<p style='font-size: 1rem; line-height: 1.6em;'>{answer}</p>"

# ── Session State ───────────────────────────────────────────────────────────
st.session_state.setdefault("page", "ask")
st.session_state.setdefault("question_input", "")
st.session_state.setdefault("history", [])
st.session_state.setdefault("last_answer", None)

# ── Stream Answer from vLLM ─────────────────────────────────────────────────
def stream_answer(prompt: str, history: list) -> str:
    payload = {
        "model": "mistralai/Mistral-7B-Instruct-v0.3",
        "messages": history + [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 256,
        "stream": True
    }

    answer = ""
    placeholder = st.empty()

    with requests.post(f"{API_URL}/chat/completions", json=payload, stream=True) as resp:
        resp.raise_for_status()
        for line in resp.iter_lines():
            if not line or line == b"data: [DONE]":
                continue
            delta = line.decode("utf-8").removeprefix("data: ")
            content = json.loads(delta)["choices"][0]["delta"].get("content", "")
            answer += content
            placeholder.markdown(format_answer(answer), unsafe_allow_html=True)
            time.sleep(0.008)
    return answer.strip()

# ── Chat Interface ──────────────────────────────────────────────────────────
def ask_page():
    st.title("📚 LLM Assistant - Ask Anything")

    question_input = st.text_input("❓ Enter your question", key="question_input")

    if st.session_state.get("last_answer"):
        formatted = format_answer(st.session_state.last_answer)
        st.markdown(formatted, unsafe_allow_html=True)
        st.session_state.last_answer = None

    if st.button("Get Answer"):
        question = question_input.strip()
        if not question:
            st.warning("Please enter a question.")
            return

        answer = stream_answer(question, st.session_state.history)
        st.session_state.history.extend([
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer}
        ])
        st.session_state.last_answer = answer
        st.rerun()

    if st.button("🕓 Show Chat History"):
        show_history()

    if st.button("🔄 Clear History"):
        st.session_state.history = []
        st.rerun()

# ── Chat History Viewer ─────────────────────────────────────────────────────
def show_history():
    st.subheader("📜 Chat History (this session)")
    if not st.session_state.history:
        st.info("No history yet.")
        return
    for msg in reversed(st.session_state.history):
        prefix = "🧑 You" if msg["role"] == "user" else "🤖 Assistant"
        st.markdown(f"**{prefix}:** {msg['content']}")
        st.markdown("---")

# ── Render ──────────────────────────────────────────────────────────────────
def render():
    ask_page()

render()
