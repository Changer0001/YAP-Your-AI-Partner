import os
import logging
from dotenv import load_dotenv
from openai import OpenAI
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
from transformers import logging as hf_logging
from huggingface_hub import login

# ✅ Logging & Env
hf_logging.set_verbosity_error()
load_dotenv()
logging.basicConfig(filename="app.log", filemode="a", level=logging.DEBUG)

# ✅ OpenAI
client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ✅ HF phi-2
login(token=os.getenv("HF_API_TOKEN"))
hf_model_id = "microsoft/phi-2"
hf_tokenizer = AutoTokenizer.from_pretrained(hf_model_id)
hf_tokenizer.pad_token = hf_tokenizer.eos_token
hf_model = AutoModelForCausalLM.from_pretrained(hf_model_id)
hf_pipe = pipeline("text-generation", model=hf_model, tokenizer=hf_tokenizer, return_full_text=False)

def ask_llm_openai(question, context):
    prompt = f"""Answer the question based only on the information provided in the context below.
If the answer cannot be found in the context, say 'I don't know.'

Context:
{context}

Question:
{question}
Answer:
"""
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

def ask_llm_hf(question, context):
    prompt = f"""Answer the question based only on the information provided in the context below.
If the answer cannot be found in the context, say 'I don't know.'

Context:
{context}

Question:
{question}
Answer:
"""
    logging.debug(f"Prompt sent to HF model:\n{prompt}")
    response = hf_pipe(prompt, max_new_tokens=150, do_sample=True, temperature=0.7)
    answer = response[0]['generated_text'].strip()
    logging.debug(f"Generated answer (HF): {answer}")
    return answer
