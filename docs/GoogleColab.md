In order to fasten the answer generation, migrated to vLLM,
Since migration to vLLM, WSL has been installed created a new python env within Ubuntu,
vLLLM does not run CPU, so Google Colab has been utilized and purchased 49.99$ plan to use CUDA GPU (A100)
Mistra 7B model requires larger GPU like A100,
Mistra 7B model installed in Cloud.....

# 🚀 vLLM + Mistral-7B-Instruct Setup on Google Colab

This document summarizes the steps taken to run the `mistralai/Mistral-7B-Instruct-v0.3` model using `vLLM` in a Google Colab notebook.

---

## ✅ 1. Hugging Face Setup

### Step 1.1: Request Access to Mistral-7B
- Visit: https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3
- Click "Request Access" (done once and approved by Hugging Face)

### Step 1.2: Generate API Token
- Go to: https://huggingface.co/settings/tokens
- Generate a **new token** with the following permissions:
  - ✅ Read access to public gated repos
  - ✅ Inference → Make calls to Inference Providers
- (Optional but safe) Keep all other permissions unchecked for minimal access.

---

## ⚙️ 2. Environment Preparation

### Step 2.1: Install `vllm` and dependencies
Run the following in a Colab code cell:

bash
!pip install --upgrade vllm


##3. Set Hugging Face Token in Environment
Use Python to export the token into the environment so that vLLM can use it to download the gated model:

python
Copy
Edit
import os
os.environ["HUGGING_FACE_HUB_TOKEN"] = "hf_your_actual_token_here"

## 4. Launch vLLM OpenAI-Compatible API Server
In the same cell or a new one, run:

bash
Copy
Edit
!HUGGING_FACE_HUB_TOKEN=hf_your_actual_token_here \
  python3 -m vllm.entrypoints.openai.api_server \
  --model mistralai/Mistral-7B-Instruct-v0.3 \
  --host 0.0.0.0 \
  --port 8000
This launches a vLLM-powered OpenAI-compatible API server using the Mistral 7B model.

## 🧠 5. Notes
You must restart the Colab runtime after installing vllm for changes to take effect.

If you get 401 Unauthorized, double-check:

The token is correctly set.

The permissions include gated repo access.

The token is passed into vLLM (via env var or HF config).

You can now call your vLLM server using the OpenAI-compatible /v1/chat/completions endpoint.
