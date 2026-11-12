FROM python:3.15.1-alpine@sha256:54448f67d7c31c39e5cdd3ea2d6382395ce142806c284425f8e897d78a0465b3 AS build

# uv from PyPI, hash-checked (requirements-uv.txt says why). Used in this
# stage only: the runtime stage gets the finished virtualenv.
COPY requirements-uv.txt /tmp/
RUN pip install --no-cache-dir --root-user-action=ignore --require-hashes -r /tmp/requirements-uv.txt
# Install exactly what uv.lock pins, checking its hashes, rather than
# re-resolving pyproject.toml at build time. While this uv matches the uv_build
# range in pyproject.toml, uv builds the project with its built-in backend and
# fetches nothing from PyPI. Bytecode is compiled here because the runtime
# image sets PYTHONDONTWRITEBYTECODE.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_PYTHON=/usr/local/bin/python3 UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_NO_CACHE=1
WORKDIR /tmp/build
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src/ src/
RUN uv sync --locked --no-dev --no-editable

FROM python:3.15.1-alpine@sha256:54448f67d7c31c39e5cdd3ea2d6382395ce142806c284425f8e897d78a0465b3
COPY --from=build /opt/venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
# The base image's pip (with the packages it vendors) and ensurepip's
# bundled pip wheel are never used at run time; removing them keeps their
# CVEs out of the image.
RUN /usr/local/bin/python3 -m pip uninstall -y --root-user-action=ignore pip \
    && rm -rf /usr/local/lib/python3*/ensurepip
# The working directory must exist at runtime: Docker recreates a missing one,
# Cloud Run fails to start the job.
WORKDIR /

# Runs as an unprivileged user; the code and virtualenv stay root-owned and
# read-only to it. The only write is STATE_PATH: on Cloud Run a Cloud Storage
# FUSE mount, mounted with uid=1000,gid=1000 so its files belong to this user.
# Elsewhere, mount a directory that uid 1000 can write.
ENV STATE_PATH=/state/last-guid.txt
USER 1000:1000
ENTRYPOINT ["apple-release-notifier"]
