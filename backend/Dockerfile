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

# Copy application code
COPY . .

# Create sessions directory
RUN mkdir -p /app/sessions

# Expose port (Railway uses PORT env var)
EXPOSE ${PORT:-8000}

# Health check - Railway sets PORT env var
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/health || exit 1

# Use shell form to expand PORT environment variable
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
