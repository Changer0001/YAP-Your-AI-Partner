import streamlit as st
import requests
import time

# FastAPI base URL
FASTAPI_URL = "http://127.0.0.1:8000"

# Set page config
st.set_page_config(page_title="LLM Assistance", layout="centered")
st.title("📚 LLM Assistance - Business QA")

# Sidebar
st.sidebar.header("⚙️ Settings")
provider = st.sidebar.radio("Choose LLM Provider", ["hf"], index=0)

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "prev_question" not in st.session_state:
    st.session_state.prev_question = ""
if "current_question" not in st.session_state:
    st.session_state.current_question = ""
if "clear_input_flag" not in st.session_state:
    st.session_state.clear_input_flag = False

# Ask Section
st.header("❓ Ask a Question")

# Clear input box if flag is set
if st.session_state.clear_input_flag:
    st.session_state.current_question = ""
    st.session_state.clear_input_flag = False

st.text_input("Enter your question", key="current_question")

# Track and update previous question
if st.session_state.prev_question != st.session_state.current_question:
    st.session_state.prev_question = st.session_state.current_question

# Handle Answer
if st.button("Get Answer"):
    question_text = st.session_state.current_question.strip()
    if not question_text:
        st.warning("Please enter a question first.")
    else:
        with st.spinner("Generating answer..."):
            try:
                payload = {"question": question_text, "provider": provider}
                response = requests.post(f"{FASTAPI_URL}/ask", json=payload)

                if response.status_code == 404:
                    st.error("❌ No relevant context found.")
                else:
                    response.raise_for_status()
                    result = response.json()

                    # Add to chat history
                    st.session_state.chat_history.append({
                        "question": question_text,
                        "answer": result["answer"],
                        "context": result["context_snippet"]
                    })

                    # ✅ Set flag to clear input on next run
                    st.session_state.clear_input_flag = True
                    st.rerun()

            except Exception as e:
                st.error(f"❌ Error during answering: {e}")

# Show chat history (latest on top)
if st.session_state.chat_history:
    st.markdown("### 💬 Chat History")

    reversed_history = list(reversed(st.session_state.chat_history))
    for i, turn in enumerate(reversed_history):
        st.markdown(f"**🧑 You:** {turn['question']}")

        if i == 0:
            # Animate only the latest answer
            answer_placeholder = st.empty()
            animated_answer = ""
            for word in turn["answer"].split():
                animated_answer += word + " "
                answer_placeholder.markdown(f"**🤖 Answer:** {animated_answer}▌")
                time.sleep(0.01)
        else:
            # Show older answers instantly
            st.markdown(f"**🤖 Answer:** {turn['answer']}")

        with st.expander("📄 Context Used", expanded=False):
            st.code(turn["context"])

    st.markdown("---")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("Built with ❤️ by Burak & Sarah")
