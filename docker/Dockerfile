# supports both variant S and variant A

FROM python:3.14-slim AS base

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# ============================================
# Variant S (Synchronous) - Django REST Framework + Gunicorn
# ============================================
FROM base AS variant-s

# Copy shared code and variant-specific code
COPY shared/ /app/shared/
COPY variant_s/ /app/variant_s/

RUN pip install --no-cache-dir -r /app/variant_s/requirements.txt

# expose Gunicorn port
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/health/ || exit 1

CMD ["sh", "-c", "cd variant_s && python manage.py migrate && gunicorn -c gunicorn_config.py config.wsgi:application"]

# ============================================
# Variant A (Asynchronous) - ADRF + Uvicorn
# ============================================
FROM base AS variant-a

# copy shared code and variant-specific code
COPY shared/ /app/shared/
COPY variant_a/ /app/variant_a/

RUN pip install --no-cache-dir -r /app/variant_a/requirements.txt

# expose Uvicorn port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8001/api/health/ || exit 1

CMD ["sh", "-c", "cd variant_a && python manage.py migrate && uvicorn --host 0.0.0.0 --port 8001 config.asgi:application"]

