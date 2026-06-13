# Typical infrastructure MVP — production-like image
# Python 3.11 slim base
FROM python:3.11-slim

WORKDIR /app

# Non-root user for security
RUN adduser --disabled-password --gecos "" appuser

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code
COPY app/ ./app/
COPY skill_assessment/ ./skill_assessment/
COPY psychological_testing/ ./psychological_testing/
COPY static/ ./static/

# SQLite DB path (override via env)
ENV SQLITE_PATH=/app/data/app.db

# Create data dir for SQLite persistence
RUN mkdir -p /app/data && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Run with uvicorn (no --reload in production)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
