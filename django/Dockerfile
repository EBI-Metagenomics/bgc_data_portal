FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    gcc \
    build-essential \
    python3-dev \
    libffi-dev \
    libssl-dev \
    make \
    git \
    libxrender1 \
    libxext6 \
    libsm6 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements-web.txt .
RUN pip install --upgrade pip && pip install -r requirements-web.txt

COPY . .

EXPOSE 8000
ENV PYTHONUNBUFFERED=0

RUN python manage.py collectstatic --noinput || true
