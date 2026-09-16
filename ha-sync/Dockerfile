ARG PYTHON_IMAGE=python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
FROM ${PYTHON_IMAGE}

# Debian security fixes; keep exact versions reviewable and fail if unavailable.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        perl-base=5.40.1-6+deb13u1 \
        gzip=1.13-1+deb13u1 \
        libpcre2-8-0=10.46-1~deb13u2 \
        libsqlite3-0=3.46.1-7+deb13u2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY ha-sync/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ha-sync ./ha-sync
COPY semantic_core ./semantic_core
COPY sources ./sources
COPY storage ./storage

CMD ["python", "-u", "ha-sync/sync.py"]
