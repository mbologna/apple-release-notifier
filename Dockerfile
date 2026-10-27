FROM ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 AS uv

FROM python:3.14.8-alpine@sha256:f6a589d43c42b9e7f7dc67a12d37132491f362859a5d750607710cc56da3bc72 AS build

# Runtime dependencies come from uv.lock, pinned with hashes, so the image gets
# exactly what was locked and tested instead of a fresh resolution of
# pyproject.toml. While this uv matches the uv_build range in pyproject.toml, uv
# builds the wheel with its built-in backend and fetches nothing from PyPI.
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1
WORKDIR /build
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ src/
RUN uv export --frozen --no-dev --no-emit-project --format requirements.txt -o /dist/requirements.txt \
    && uv build --wheel -o /dist

FROM python:3.14.8-alpine@sha256:f6a589d43c42b9e7f7dc67a12d37132491f362859a5d750607710cc56da3bc72

# Installed from a throwaway directory. The working directory must still exist
# at runtime: Docker recreates a missing one, Cloud Run fails to start the job.
COPY --from=build /dist/ /tmp/dist/
RUN pip install --no-cache-dir --require-hashes -r /tmp/dist/requirements.txt \
    && pip install --no-cache-dir --no-deps --no-index /tmp/dist/*.whl \
    && rm -rf /tmp/dist
WORKDIR /

# Runs as root, like the job's previous stock python image: on Cloud Run the
# state directory is a Cloud Storage FUSE mount, and a non-root user has not
# been tested against its permissions yet.
ENV STATE_PATH=/state/last-guid.txt PYTHONUNBUFFERED=1
ENTRYPOINT ["apple-release-notifier"]
