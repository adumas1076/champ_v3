# ============================================
# CHAMP V3 — Brain Service
# FastAPI server: persona + mode detection + LiteLLM router
# ============================================
FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libffi-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-brain.txt .
RUN pip install --no-cache-dir -r requirements-brain.txt

COPY brain/ ./brain/
COPY mind/ ./mind/
COPY self_mode/ ./self_mode/
COPY persona/ ./persona/
COPY hands/ ./hands/

EXPOSE 8100

CMD ["sh", "-c", "python -m uvicorn brain.main:app --host 0.0.0.0 --port ${PORT:-8100}"]
