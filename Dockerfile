FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV HERMES_LLM_PROVIDER=openai_compatible
ENV HERMES_LLM_BASE_URL=https://api.openai.com/v1
ENV HERMES_LLM_MODEL=gpt-4o-mini

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY docs ./docs
COPY tests ./tests
COPY scripts ./scripts

RUN pip install --no-cache-dir build && \
    python -m build --wheel --no-isolation && \
    pip install --no-cache-dir dist/*.whl && \
    rm -rf dist build

EXPOSE 8765

CMD ["python", "-m", "hermes_os.command_center.api"]
