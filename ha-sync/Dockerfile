FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY ha-sync/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ha-sync ./ha-sync
COPY semantic_core ./semantic_core
COPY sources ./sources
COPY storage ./storage

CMD ["python", "-u", "ha-sync/sync.py"]
