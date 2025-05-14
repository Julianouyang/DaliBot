# syntax=docker/dockerfile:1

# -----------------------------
# Build stage (optional – using a single stage here because we only need Python deps)
# -----------------------------
FROM python:3.11-slim AS runtime

# Prevent Python from writing .pyc files and enable unbuffered stdout/err
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install system-level dependencies required for building wheels (e.g. pillow) and cleaning up afterwards
RUN apt-get update \
    && apt-get install -y --no-install-recommends git build-essential gcc libjpeg62-turbo-dev zlib1g-dev libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Only copy requirement files first to leverage Docker layer caching
COPY requirements.txt ./

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the project source code
COPY . .

# Expose the port used by Telegram webhook (default 8443)
EXPOSE 8443

# The application expects the following environment variables to be supplied at runtime:
#   TELEGRAM_TOKEN  – Telegram Bot token
#   OPENAI_TOKEN    – OpenAI API key
#   HEROKU_DOMAIN   – Fully-qualified public domain used for webhook callbacks (optional)
# When running locally inside the container we can use long-polling instead of a webhook by passing --use-local.

CMD ["python", "source/main.py"] 