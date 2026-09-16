ARG NEO4J_IMAGE=neo4j:5.26-community@sha256:bb268a2f1b4f3c79e4bd1a00a82a6e63bbd4fcc4088da03c1b2380655f256cb2
FROM ${NEO4J_IMAGE}

# Debian security fixes; keep exact versions reviewable and fail if unavailable.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        perl-base=5.40.1-6+deb13u1 \
        gzip=1.13-1+deb13u1 \
        libpcre2-8-0=10.46-1~deb13u2 \
        libsqlite3-0=3.46.1-7+deb13u2 \
    && rm -rf /var/lib/apt/lists/*
