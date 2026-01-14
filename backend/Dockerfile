FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# ML features disabled - torch/sentence-transformers removed to reduce memory usage
# To re-enable: uncomment torch install and ML dependencies in requirements.txt
# RUN pip install --no-cache-dir torch==2.1.2 --index-url https://download.pytorch.org/whl/cpu

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code (cache bust: 2026-01-14T18:58:00Z - ML disabled)
COPY . .

# Create sessions directory
RUN mkdir -p /app/sessions

# Expose port (Railway will assign actual port via PORT env var)
EXPOSE 8000

# Railway manages healthchecks - removed HEALTHCHECK directive

# Use shell form to allow PORT environment variable expansion
# Railway sets PORT dynamically; default to 8000 if not set
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port \${PORT:-8000}"
