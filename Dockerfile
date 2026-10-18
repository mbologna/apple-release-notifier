FROM python:3.14.8-alpine@sha256:f6a589d43c42b9e7f7dc67a12d37132491f362859a5d750607710cc56da3bc72

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/
RUN pip install --no-cache-dir . && rm -rf /app

# Runs as root, like the job's previous stock python image: on Cloud Run the
# state directory is a Cloud Storage FUSE mount, and a non-root user has not
# been tested against its permissions yet.
ENV STATE_PATH=/state/last-guid.txt PYTHONUNBUFFERED=1
ENTRYPOINT ["apple-release-notifier"]
