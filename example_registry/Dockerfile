# syntax=docker/dockerfile:1
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set work directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock README.md ./

# Sync dependencies (no dev deps, no project install)
RUN uv sync --no-dev --no-install-project --extra web

# Copy application code
COPY main.py function_discovery.py models.py ./
COPY functions/ ./functions/

# Expose port
EXPOSE 9999

# Run the application (python is in venv path)
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9999"]
