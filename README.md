# LLM_Assistance

# Business LLM Assistant (Prototype)

## Objective

This project is a prototype for building lightweight, domain-specific LLM (Large Language Model) assistants for small businesses.

The goal is to create customized AI assistants that can answer questions using a business' internal data - such FAQs, websites, or policy documents - without needing to train large models from scratch.

## How It Works

We use **RAG (Retrieval - Augmented Generation)** to enhance a base LLM with business-specific data:
- Ingest and chunk internal documents
- Generate embeddings and store them in a vector database (e.g., Chroma)
- Use a lightweight LLM(like 'phi-2' or OpenAI API) to answer user questions using retrieved chunks

This approach works without a GPU and runs locally or on lightweight infrastructure.

