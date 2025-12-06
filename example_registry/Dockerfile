# syntax=docker/dockerfile:1
FROM python:3.13-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Set work directory
WORKDIR /app

# Install dependencies directly (no project context)
RUN uv pip install --system fastapi uvicorn pydantic

# Copy application code only (no pyproject.toml to avoid project detection)
COPY main.py function_discovery.py models.py ./
COPY functions/ ./functions/

# Expose port
EXPOSE 9999

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9999"]
