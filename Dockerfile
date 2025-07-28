# Dockerfile for Challenge 1b: Persona-Driven Document Intelligence

FROM --platform=linux/amd64 python:3.10-slim

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements (if exists) and install
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source code
COPY . .

# Expose no ports (runs as batch job)

# Entry point
CMD ["python", "ollama_integration.py"]
