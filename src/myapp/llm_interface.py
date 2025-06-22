import os
import logging
import re
from dotenv import load_dotenv
from transformers import (
    AutoTokenizer,
    pipeline,
    logging as hf_logging
)
from optimum.onnxruntime import ORTModelForSeq2SeqLM

# ✅ Load environment variables
load_dotenv()

# ✅ Configure logging
logging.basicConfig(filename="app.log", filemode="a", level=logging.DEBUG)
hf_logging.set_verbosity_error()

# ✅ Hugging Face model setup (ONNX quantized for CPU)
hf_model_id = "google/flan-t5-small"

try:
    hf_tokenizer = AutoTokenizer.from_pretrained(hf_model_id)

    hf_model = ORTModelForSeq2SeqLM.from_pretrained(
        hf_model_id,
        export=True,
        provider="CPUExecutionProvider"
    )

    hf_pipe = pipeline(
        "text2text-generation",
        model=hf_model,
        tokenizer=hf_tokenizer
    )

    logging.info("✅ Quantized Hugging Face model loaded using ONNX Runtime.")

except Exception as e:
    logging.exception("❌ Failed to load quantized Hugging Face model:")
    hf_pipe = None

# ✅ Inference function
def ask_llm_hf(question, context):
    if not hf_pipe:
        return "Quantized Hugging Face model not available."

    prompt = f"""Answer the question based only on the information provided in the context below.
If the answer cannot be found in the context, say 'I don't know.'

Context:
{context}

Question:
{question}
Answer:"""

    logging.debug(f"Prompt sent to HF model:\n{prompt}")
    try:
        response = hf_pipe(prompt, max_new_tokens=100)
        answer = response[0]["generated_text"].strip()
        logging.debug(f"Generated answer (HF Quantized): {answer}")
        return answer
    except Exception as e:
        logging.error(f"❌ Failed to generate answer: {e}")
        return f"Sorry, failed to get answer from Hugging Face: {e}"

# ✅ Check for incomplete answers
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

# ✅ Complete-answer generator with retry
def get_complete_answer(question, context, provider='hf', max_tries=2):
    if provider != 'hf':
        return "Only 'hf' provider supported in this module."

    answer = ask_llm_hf(question, context)
    tries = 1

    while is_incomplete(answer) and tries < max_tries:
        logging.info(f"[Try {tries}] Incomplete answer detected. Regenerating...")
        followup_prompt = f"{answer.strip()}\nContinue the answer:"
        try:
            extension = hf_pipe(followup_prompt, max_new_tokens=100)
            answer += " " + extension[0]["generated_text"].strip()
        except Exception as e:
            logging.error(f"❌ Failed during continuation: {e}")
            break
        tries += 1

    return answer.strip()
