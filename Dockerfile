# ----------------------------
# Base image
# ----------------------------
FROM python:3.12-slim

# ----------------------------
# Environment variables
# ----------------------------
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    APP_HOME=/app \
    PIP_NO_CACHE_DIR=1 \
    POETRY_VIRTUALENVS_CREATE=false

# ----------------------------
# Set working directory
# ----------------------------
WORKDIR $APP_HOME

# ----------------------------
# System dependencies
# ----------------------------
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        libpq-dev \
        wget \
    && rm -rf /var/lib/apt/lists/*

# ----------------------------
# Copy project files
# ----------------------------
COPY . $APP_HOME

# ----------------------------
# Install Python dependencies
# ----------------------------
RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# ----------------------------
# Create logs directory
# ----------------------------
RUN mkdir -p $APP_HOME/logs

# ----------------------------
# Expose FastAPI port
# ----------------------------
EXPOSE 8000

# ----------------------------
# Entrypoint script for readiness check (optional)
# ----------------------------
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# ----------------------------
# Command
# ----------------------------
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
