# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install dependencies (no dev, no editable install of project itself)
RUN uv sync --frozen --no-install-project --no-dev

# Copy application code
COPY app.py ./

# Create a non-root user to run the application
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port 8080
EXPOSE 8080

# Run the application with gunicorn
CMD ["uv", "run", "gunicorn", "app:app", "-b", "0.0.0.0:8080", "--workers", "4", "--timeout", "120"]
