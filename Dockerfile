FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Create non-root user for security
RUN useradd -m -u 1000 paperlessbot && \
    chown -R paperlessbot:paperlessbot /app

# Switch to non-root user
USER paperlessbot

# Set default environment variables
ENV LOG_LEVEL=INFO \
    PYTHONPATH=/app/src \
    HEALTH_PORT=8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

# Expose health check port
EXPOSE 8080

# Default: run the bot
CMD ["python", "-m", "paperless_bot", "run"]
