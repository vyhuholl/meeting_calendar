# Use the official uv image with Python 3.14 Alpine
FROM ghcr.io/astral-sh/uv:python3.14-alpine

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev

# Copy application code
COPY app/ ./app/
COPY ui/ ./ui/

# Expose ports: 8000 for the API, 8501 for the Streamlit UI.
# The image serves both processes; docker-compose selects the command per service.
EXPOSE 8000 8501

# Default command runs the API; the UI service overrides it in docker-compose.
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]