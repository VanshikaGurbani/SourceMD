FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for psycopg2, sentence-transformers, and pypdf.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching.
COPY backend/requirements.txt /app/backend/requirements.txt

# Install CPU-only PyTorch first to avoid the 2.5 GB CUDA build.
RUN pip install --upgrade pip && \
    pip install torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install -r /app/backend/requirements.txt

# Copy the rest of the backend package.
COPY backend /app/backend

EXPOSE 8080

# The application is imported as `backend.main:app` from /app.
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
