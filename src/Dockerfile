FROM python:3.10-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir optimum[onnxruntime] onnxruntime

# Copy application code
COPY myapp/ ./myapp/

# Set PYTHONPATH so FastAPI and modules resolve correctly
ENV PYTHONPATH=/app

# Optionally initialize DB
# If you want to run init_db() once at container startup, create `init.py` and call it here:
# RUN python myapp/init_db.py

# Expose FastAPI port
EXPOSE 8000

# Start FastAPI server
CMD ["uvicorn", "myapp.app:api", "--host", "0.0.0.0", "--port", "8000"]
