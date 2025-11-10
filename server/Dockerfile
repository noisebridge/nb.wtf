# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install pipenv
RUN pip install --no-cache-dir pipenv

# Copy Pipfile and Pipfile.lock
COPY Pipfile Pipfile.lock ./

# Install dependencies from Pipfile.lock
# --deploy ensures Pipfile.lock is up to date with Pipfile
# --system installs packages to the system python rather than creating a virtualenv
RUN pipenv install --deploy --system

# Copy application code
COPY app.py ./

# Create a non-root user to run the application
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port 8080
EXPOSE 8080

# Run the application with gunicorn
CMD ["gunicorn", "app:app", "-b", "0.0.0.0:8080", "--workers", "4", "--timeout", "120"]
