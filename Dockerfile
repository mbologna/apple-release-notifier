FROM python:3.14.9-alpine@sha256:dbeb11d16bb95c3a7e3c25c842cb9f20cbc8c18f8be0461a4a0dcc861ad386a0 AS build

# Runtime dependencies come from uv.lock, pinned with hashes, so the image gets
# exactly what was locked and tested instead of a fresh resolution of
# pyproject.toml. While this uv matches the uv_build range in pyproject.toml, uv
# builds the wheel with its built-in backend and fetches nothing from PyPI.
# uv from PyPI, hash-checked (requirements-uv.txt says why).
COPY requirements-uv.txt /tmp/
RUN pip install --no-cache-dir --root-user-action=ignore --require-hashes -r /tmp/requirements-uv.txt
ENV UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1
WORKDIR /build
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ src/
RUN uv export --frozen --no-dev --no-emit-project --format requirements.txt -o /dist/requirements.txt \
    && uv build --wheel -o /dist

FROM python:3.14.9-alpine@sha256:dbeb11d16bb95c3a7e3c25c842cb9f20cbc8c18f8be0461a4a0dcc861ad386a0

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
