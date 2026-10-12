FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# CPU-only torch wheel: much smaller image, and HF Spaces' free CPU tier has
# no CUDA driver for a GPU build to use anyway.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Spaces containers run as a non-root user by default; make sure our
# runtime-writable dirs (model cache, chroma's local db) are writable by it.
RUN mkdir -p /app/.cache/huggingface /app/chroma_db && chmod -R 777 /app

EXPOSE 7860

COPY start.sh .
RUN chmod +x start.sh

CMD ["./start.sh"]