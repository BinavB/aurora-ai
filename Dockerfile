FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir -e ".[serve]"

# Hosts (Render, Fly, Koyeb, Railway, Cloud Run, ...) inject $PORT.
ENV PORT=8000
EXPOSE 8000

# Bind to 0.0.0.0 so the container is reachable; honour the platform's $PORT.
CMD ["sh", "-c", "uvicorn aurora.api.__main__:app --host 0.0.0.0 --port ${PORT:-8000}"]
