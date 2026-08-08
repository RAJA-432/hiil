# hiil — RAG-backed CLI chat app.
#
# Lean runtime image for the interactive CLI. All persistent state (vector
# store, usage DB, logs) lives under /data, which is mounted as a volume; the
# container sets HOME=/data so `Path.home() / ".hiil"` resolves inside it.
#
#   Build:  docker build -t hiil .
#   Run:    docker run -it --rm -v ./data:/data hiil
#
# To run the web gate (vajra_gate) instead, override the command:
#   docker run -it --rm -p 8000:8000 hiil uvicorn vajra_gate:app --host 0.0.0.0 --port 8000

FROM python:3.13-slim

# git is required by `pip install -e .` when building from a git working tree.
# PYTHONUNBUFFERED keeps CLI/log output flowing through docker logs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Copy the project first (see .dockerignore for what is excluded).
COPY . .

# Editable install so `python main.py` and `python -m eval.*` import the live
# tree. The `ocr` extra (Pillow/pytesseract) is intentionally skipped to keep
# the image lean; add it back if OCR is needed: `pip install -e ".[ocr]"`.
RUN pip install --no-cache-dir -e .

# Non-root runtime user. HOME=/data makes ~/.hiil (vectors.db, chat.log,
# users.db, usage store) land on the mounted /data volume.
RUN useradd --create-home --uid 10001 app \
    && mkdir -p /data \
    && chown -R app:app /data

USER app
ENV HOME=/data

VOLUME /data

# Interactive CLI entrypoint (see main.py).
CMD ["python", "main.py"]
