FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch first (much smaller than GPU version)
RUN pip install --no-cache-dir torch==2.1.2 --index-url https://download.pytorch.org/whl/cpu

# Install other Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (cache bust: 2026-01-14T17:34:00Z)
COPY . .

# Create sessions directory
RUN mkdir -p /app/sessions

# Expose default port
EXPOSE 8000

# Railway manages healthchecks - removed HEALTHCHECK directive

# Hardcode port 8000 - Railway's $PORT expansion has issues with exec form
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
