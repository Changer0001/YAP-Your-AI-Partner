# LLM_Assistance

# Business LLM Assistant (Prototype)

## Objective

This project is a prototype for building lightweight, domain-specific LLM (Large Language Model) assistants for small businesses.

The goal is to create customized AI assistants that can answer questions using a business' internal data - such FAQs, websites, or policy documents - without needing to train large models from scratch.

## ✨ Features

- ✅ Uses **Retrieval-Augmented Generation (RAG)** to provide relevant answers
- ✅ Supports **internal documents, FAQs, and websites**
- ✅ No GPU required — works on lightweight servers or locally
- ✅ Extensible and customizable for any business type


## How It Works

We use **RAG (Retrieval - Augmented Generation)** to enhance a base LLM with business-specific data:
- Ingest and chunk internal documents
- Generate embeddings and store them in a vector database (e.g., Chroma)
- Use a lightweight LLM(like 'phi-2' or OpenAI API) to answer user questions using retrieved chunks

This approach works without a GPU and runs locally or on lightweight infrastructure.

# Hugging Face Inference Optimization Guide

This document summarizes the key changes made to improve the speed and stability of Hugging Face inference in your `LLM_Assistance` project running on a CPU-only system.

---

## ✅ Background

The initial setup used the `microsoft/phi-2` model, which is large and slow on CPU, and the wrong model architecture (`AutoModelForCausalLM`) was used for a T5-style model. Additionally, incorrect or deprecated Hugging Face APIs caused inference failures.

---

## 🔧 List of Key Changes

### 1. Model Switched to CPU-Friendly

```python
# Old (slow + large)
hf_model_id = "microsoft/phi-2"

# New (lightweight + fast)
hf_model_id = "google/flan-t5-small"
```

### 2. Correct Model Loader

```python
# Old (Causal Language Model)
from transformers import AutoModelForCausalLM
hf_model = AutoModelForCausalLM.from_pretrained(hf_model_id)

# New (Encoder-Decoder for T5)
from transformers import AutoModelForSeq2SeqLM
hf_model = AutoModelForSeq2SeqLM.from_pretrained(hf_model_id)
```

### 3. Correct Pipeline Type

```python
# Old (wrong for T5)
pipeline("text-generation", ...)

# New (correct for T5)
pipeline("text2text-generation", ...)
```

### 4. Removed Unsupported Argument

```python
# Removed from pipeline call:
# return_full_text=False
```

### 5. Faster Token Generation

```python
# Old
max_new_tokens = 150

# New
max_new_tokens = 100  # (or lower)
```

---

## 🧠 Additional Notes

* Avoid models over 1B parameters if running on CPU.
* `phi-2` should only be used with GPU acceleration.
* `text2text-generation` is required for all encoder-decoder models like `t5`, `flan`, `bart`, etc.
* If needed, you can add a caching layer or truncate long `context` inputs to improve speed.

---

## 💡 Recommendations

* For best performance, use a Hugging Face **inference endpoint** (Pro plan).
* Always test new models locally before production.
* Document these choices to make future upgrades smoother.
