# Docker Guide for LLM Assistant

## Dockerfile Overview

This Dockerfile builds a lightweight Python 3.10 environment for your LLM Assistant FastAPI app.

### Key Points:
- Uses the official `python:3.10-slim-bookworm` base image for a small footprint.
- Updates system packages and installs `git`.
- Installs Python dependencies from `requirements.txt`.
- Copies your application code into the container.
- Exposes port 8000 for FastAPI.
- Runs the FastAPI app with `uvicorn` on container start.
- **Does NOT** pre-download large ML models during build to avoid memory issues.

---

## Dockerfile Example

```dockerfile
FROM python:3.10-slim-bookworm

RUN apt-get update && apt-get upgrade -y && pip install --upgrade pip && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY myapp/ ./myapp/

EXPOSE 8000

CMD ["uvicorn", "myapp.app:api", "--host", "0.0.0.0", "--port", "8000"]


Run this command in the directory containing your Dockerfile:
docker build -t llm_assistant .

How to Run the Docker Container
docker run -d -p 8000:8000 --env-file .env --name llm_app llm_assistant

## Why Model Download is Done at Runtime (Not Build Time)
# Downloading large ML models during docker build uses a lot of RAM and CPU.

Your laptop (16 GB RAM) ran out of memory during this step, causing the build to fail with exit code 137.

Moving model loading to app startup reduces build time and memory use.

Initial app startup is slower (cold start), but subsequent runs are faster due to local caching.

## Tips
Keep your .env file outside the image to protect secrets.

Use .dockerignore to exclude unnecessary files and speed up build.

Consider lazy loading models inside your Python app to optimize memory.