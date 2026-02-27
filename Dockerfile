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
COPY hands/__init__.py ./hands/__init__.py
COPY hands/bridge.py ./hands/bridge.py

EXPOSE 8100

CMD ["python", "-m", "uvicorn", "brain.main:app", "--host", "0.0.0.0", "--port", "8100"]
