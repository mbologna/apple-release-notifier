FROM python:3.14.8-alpine@sha256:f6a589d43c42b9e7f7dc67a12d37132491f362859a5d750607710cc56da3bc72

# Built in a throwaway directory. The working directory must still exist at
# runtime: Docker recreates a missing one, Cloud Run fails to start the job.
COPY pyproject.toml README.md LICENSE /tmp/build/
COPY src/ /tmp/build/src/
RUN pip install --no-cache-dir /tmp/build && rm -rf /tmp/build
WORKDIR /

# Runs as root, like the job's previous stock python image: on Cloud Run the
# state directory is a Cloud Storage FUSE mount, and a non-root user has not
# been tested against its permissions yet.
ENV STATE_PATH=/state/last-guid.txt PYTHONUNBUFFERED=1
ENTRYPOINT ["apple-release-notifier"]
