FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY config.py prompts.py tracing.py evaluation.py agent.py ./

# Evaluation reports (mount a volume in Cloud Run for persistence)
RUN mkdir -p /app/runs
VOLUME ["/app/runs"]

CMD ["python", "agent.py"]
