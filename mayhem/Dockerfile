# syntax=docker/dockerfile:1.7
#
# Commit-image Dockerfile (SMALL form) on the org base image. psycopg2 is a CPython C extension over
# libpq, so the image adds what the build needs from the network at image-build time (apt: libpq-dev,
# python3-dev, a PostgreSQL server for upstream's test suite; pip: setuptools, atheris) and leaves
# mayhem/build.sh to run offline.
#
# Build (from the repo root):
#   DOCKER_BUILDKIT=1 docker build -f mayhem/Dockerfile \
#       --build-arg COMMIT=$(git rev-parse HEAD) -t psycopg2-commit:test .

FROM ghcr.io/savantenvs/base:20261023

ARG COMMIT
ARG REPO_URL
ARG SOURCE_DATE_EPOCH
ARG SANITIZER_FLAGS
ARG COVERAGE_FLAGS=
ARG MAYHEM_JOBS=

# Writable scratch under Mayhem's read-only image mount (python tempfile, postgres sockets).
ENV TMPDIR=/dev/shm

USER root
RUN [ -n "$SOURCE_DATE_EPOCH" ] && repro-sources-list.sh || true ; \
    apt-get update && apt-get install -yq --no-install-recommends \
        libpq-dev python3-dev postgresql \
 && rm -rf /var/lib/apt/lists/*
# Build-time Python deps live in the system interpreter (PEP 668 -> --break-system-packages):
# setuptools builds the extension, atheris drives the pure-Python fuzz_sql target.
RUN pip install --no-cache-dir --break-system-packages setuptools==80.9.0 atheris==3.1.0

USER mayhem
WORKDIR /mayhem
COPY --chown=2000:2000 . /mayhem

RUN if [ -x /opt/mayhem/ccache/prefill ]; then /opt/mayhem/ccache/prefill bash mayhem/build.sh; \
    else bash mayhem/build.sh; fi

RUN if [ -f mayhem/test.sh ]; then bash mayhem/test.sh; else echo "no mayhem/test.sh"; fi

LABEL org.opencontainers.image.source="${REPO_URL}" \
      org.opencontainers.image.revision="${COMMIT}" \
      rlenv.tier="commit" \
      rlenv.source_date_epoch="${SOURCE_DATE_EPOCH}" \
      rlenv.user="mayhem"

USER mayhem
WORKDIR /mayhem
