import os
import re
import time
import logging
from dotenv import load_dotenv
from huggingface_hub import InferenceClient

# ✅ Load environment variables
load_dotenv()

# ✅ Logging configuration
logging.basicConfig(filename="app.log", filemode="a", level=logging.DEBUG)

# ✅ Initialize Hugging Face Inference Client
HF_API_TOKEN = os.getenv("HF_API_TOKEN")
client = InferenceClient(model="mistralai/Mistral-7B-Instruct-v0.2", token=HF_API_TOKEN)

# ✅ Regular (non-streaming) chat-based generation
def ask_llm_hf(question, context):
    prompt = f"""Answer the following question using only the context provided.
If the answer is not in the context, say "I don't know".

Context:
{context}

Question:
{question}
"""
    try:
        start_time = time.time()
        result = client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a helpful assistant that only answers using the provided context."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.7,
        )
        elapsed = time.time() - start_time
        logging.info(f"⏱️ Answer generated in {elapsed:.2f} seconds")
        return result.choices[0].message.content.strip()
    except Exception as e:
        logging.exception("❌ Generation failed:")
        return f"❌ Error: {e}"

# ✅ Streaming support using chat API
def ask_llm_hf_stream(question, context):
    prompt = f"""Answer the following question using only the context provided.
If the answer is not in the context, say "I don't know".

Context:
{context}

Question:
{question}
"""

    try:
        stream = client.chat_completion(
            messages=[
                {"role": "system", "content": "You are a helpful assistant that only answers using the provided context."},
                {"role": "user", "content": prompt}
            ],
            stream=True,
            max_tokens=300,
            temperature=0.7
        )

        for chunk in stream:
            if chunk.choices and "content" in chunk.choices[0].delta:
                yield chunk.choices[0].delta["content"]

    except Exception as e:
        logging.exception("❌ Streaming failed:")
        yield f"\n[ERROR] {e}"


# ✅ Utility to detect incomplete answers
def is_incomplete(answer: str) -> bool:
    answer = answer.strip()
    if not answer:
        return True
    if answer[-1] not in ".!?":
        return True
    if re.search(r"\b(and|but|or|so|because)$", answer, re.IGNORECASE):
        return True
    if answer.endswith("...") or re.search(r"\b\w{1,3}$", answer):
        return True
    return False

# ✅ Fallback logic for incomplete responses
def get_complete_answer(question, context, provider='hf', max_tries=2):
    if provider != 'hf':
        return "Only 'hf' provider supported in this module."

    answer = ask_llm_hf(question, context)
    tries = 1

    while is_incomplete(answer) and tries < max_tries:
        logging.info(f"[Try {tries}] Incomplete answer detected. Retrying...")
        followup = f"{answer.strip()}\nContinue the answer:"
        try:
            continuation = client.chat_completion(
                messages=[
                    {"role": "user", "content": followup}
                ],
                max_tokens=100,
                temperature=0.7
            )
            answer += " " + continuation.choices[0].message.content.strip()
        except Exception as e:
            logging.exception("❌ Error during regeneration:")
            break
        tries += 1

    return answer.strip()
