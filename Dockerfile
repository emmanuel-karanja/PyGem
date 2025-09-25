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
# Copy only dependency files first (for caching)
# ----------------------------
COPY requirements.txt $APP_HOME/

# ----------------------------
# Install Python dependencies
# ----------------------------
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# ----------------------------
# Copy the rest of the project
# ----------------------------
COPY . $APP_HOME

# ----------------------------
# Create logs directory
# ----------------------------
RUN mkdir -p $APP_HOME/logs

# ----------------------------
# Expose FastAPI port
# ----------------------------
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
