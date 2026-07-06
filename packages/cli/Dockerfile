FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY packages/sdk-python /tmp/sdk-python
COPY packages/cli /tmp/cli

RUN pip install --no-cache-dir /tmp/sdk-python /tmp/cli

ENTRYPOINT ["ambrosia"]
CMD ["--help"]
