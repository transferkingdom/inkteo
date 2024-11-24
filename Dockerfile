FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Virtual environment oluştur ve aktifleştir
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Requirements yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn whitenoise

# Önce static dizini oluştur
RUN mkdir -p /app/staticfiles /app/static /app/media
RUN chmod -R 755 /app/staticfiles /app/static /app/media

# Tüm projeyi kopyala
COPY . .

# Static dosyaları topla
RUN python manage.py collectstatic --noinput --clear

EXPOSE 80

# Gunicorn başlat
CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:80", "--workers", "3"]