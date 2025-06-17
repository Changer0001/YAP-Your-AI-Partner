import os
import logging
from dotenv import load_dotenv
from openai import OpenAI
from transformers import (
    AutoTokenizer,
    AutoModelForSeq2SeqLM,
    pipeline,
    logging as hf_logging
)

# ✅ Load environment variables
load_dotenv()

# ✅ Configure logging
logging.basicConfig(filename="app.log", filemode="a", level=logging.DEBUG)
hf_logging.set_verbosity_error()

# ✅ Initialize OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    client_openai = OpenAI(api_key=OPENAI_API_KEY)
    logging.info("OpenAI client initialized.")
else:
    client_openai = None
    logging.warning("OPENAI_API_KEY not set. OpenAI client will be skipped.")

# ✅ Hugging Face model setup for CPU (use smaller model)
hf_model_id = "google/flan-t5-small"  # Faster for CPU

# ✅ Load tokenizer and model (no torch_dtype, no device_map)
hf_tokenizer = AutoTokenizer.from_pretrained(hf_model_id)
hf_model = AutoModelForSeq2SeqLM.from_pretrained(hf_model_id)

# ✅ Setup text2text-generation pipeline
hf_pipe = pipeline(
    "text2text-generation",
    model=hf_model,
    tokenizer=hf_tokenizer
)

# ✅ OpenAI wrapper
def ask_llm_openai(question, context):
    if not client_openai:
        logging.warning("OpenAI client not initialized, skipping call.")
        return "OpenAI API key not provided. Skipping OpenAI response."

    prompt = f"""Answer the question based only on the information provided in the context below.
If the answer cannot be found in the context, say 'I don't know.'

Context:
{context}

Question:
{question}
Answer:"""

    logging.debug(f"Prompt sent to OpenAI:\n{prompt}")
    response = client_openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant for answering business questions."},
            {"role": "user", "content": prompt},
        ],
        max_tokens=300,
    )
    answer = response.choices[0].message.content.strip()
    logging.debug(f"Generated answer (OpenAI): {answer}")
    return answer

# ✅ HF wrapper
def ask_llm_hf(question, context):
    prompt = f"""Answer the question based only on the information provided in the context below.
If the answer cannot be found in the context, say 'I don't know.'

Context:
{context}

Question:
{question}
Answer:"""

    logging.debug(f"Prompt sent to HF model:\n{prompt}")
    try:
        response = hf_pipe(prompt, max_new_tokens=100)  # ← Reduce max tokens for speed
        answer = response[0]["generated_text"].strip()
        logging.debug(f"Generated answer (HF): {answer}")
        return answer
    except Exception as e:
        logging.error(f"Failed to get answer from Hugging Face: {e}")
        return f"Sorry, failed to get answer from Hugging Face: {e}"
