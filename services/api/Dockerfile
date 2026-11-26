# Build context là GỐC REPO để image chứa được data/seed/:
#   docker build -f services/api/Dockerfile -t ringforge-api .
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SEED_DIR=/srv/data/seed

WORKDIR /srv

COPY services/api/requirements.txt .
RUN pip install -r requirements.txt

COPY services/api/app ./app

RUN useradd --create-home --uid 10001 appuser
USER appuser

# Render/Railway đặt biến PORT; local mặc định 8000.
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
