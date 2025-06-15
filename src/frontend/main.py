import streamlit as st
import requests

# Configure FastAPI base URL
FASTAPI_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="LLM Assistance", layout="centered")

st.title("📚 LLM Assistance - Business QA")

st.sidebar.header("⚙️ Settings")
provider = st.sidebar.radio("Choose LLM Provider", ["openai", "hf"], index=0)

# Ingest Section
st.header("📂 Document Ingestion")
with st.form("ingest_form"):
    folder_path = st.text_input("Folder path to documents", value="C:/Users/Burak/Documents/GitHub/LLM_Assistance/data/example_business_docs")
    ingest_submit = st.form_submit_button("Ingest Documents")

    if ingest_submit:
        with st.spinner("Ingesting documents..."):
            try:
                response = requests.post(f"{FASTAPI_URL}/ingest", json={"folder_path": folder_path})
                response.raise_for_status()
                st.success(f"✅ Ingested {response.json().get('documents_ingested')} documents successfully!")
            except Exception as e:
                st.error(f"❌ Error during ingestion: {e}")

# Ask Section
st.header("❓ Ask a Question")
question = st.text_input("Enter your question")

if st.button("Get Answer"):
    if not question.strip():
        st.warning("Please enter a question first.")
    else:
        with st.spinner("Generating answer..."):
            try:
                payload = {"question": question, "provider": provider}
                response = requests.post(f"{FASTAPI_URL}/ask", json=payload)
                if response.status_code == 404:
                    st.error("❌ No relevant context found.")
                else:
                    response.raise_for_status()
                    result = response.json()
                    st.success("✅ Answer generated:")
                    st.write(result['answer'])
                    with st.expander("📄 Context Used"):
                        st.code(result['context_snippet'])
            except Exception as e:
                st.error(f"❌ Error during answering: {e}")

st.sidebar.markdown("---")
st.sidebar.markdown("Built with ❤️ by Burak & Sarah")

