FROM python:3.10-slim-bookworm

# Upgrade pip and install OS dependencies
RUN apt-get update && apt-get upgrade -y && pip install --upgrade pip && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to use Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir optimum[onnxruntime] onnxruntime  # ✅ Add this line

# Copy the application code into the Docker image
COPY myapp/ ./myapp/

# Ensure the Python interpreter can find your modules
ENV PYTHONPATH=/app

# Expose the port for FastAPI
EXPOSE 8000

# Run the FastAPI app
CMD ["uvicorn", "myapp.app:api", "--host", "0.0.0.0", "--port", "8000"]
