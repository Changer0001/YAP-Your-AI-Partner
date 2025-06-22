import os
import logging
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

    # Load quantized ONNX model for CPU (export if needed)
    hf_model = ORTModelForSeq2SeqLM.from_pretrained(
        hf_model_id,
        export=True,
        provider="CPUExecutionProvider"
    )

    # Text generation pipeline using quantized model
    hf_pipe = pipeline(
        "text2text-generation",
        model=hf_model,
        tokenizer=hf_tokenizer
    )

    logging.info("✅ Quantized Hugging Face model loaded using ONNX Runtime.")

except Exception as e:
    logging.exception("❌ Failed to load quantized Hugging Face model:")
    hf_pipe = None


# ✅ Inference wrapper for Hugging Face model
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
