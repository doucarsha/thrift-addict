FROM mcr.microsoft.com/playwright/python:v1.64.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Playwright browsers are baked into the base image; ensure chromium exists
RUN python -m playwright install chromium --only-shell 2>/dev/null || true

EXPOSE 10000

# Single worker (one browser instance), generous timeout for scrapes
CMD gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120
