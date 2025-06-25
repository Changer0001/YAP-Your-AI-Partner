FROM python:3.10-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY myapp/ ./myapp/

# Set PYTHONPATH so FastAPI resolves imports correctly
ENV PYTHONPATH=/app

# Expose FastAPI port
EXPOSE 8000

# Start FastAPI server
CMD ["uvicorn", "myapp.app:api", "--host", "0.0.0.0", "--port", "8000"]
