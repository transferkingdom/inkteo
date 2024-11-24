FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DJANGO_SETTINGS_MODULE=core.settings

WORKDIR /app

# Sistem paketlerini yükle
RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn whitenoise

# Dizin yapısını oluştur
RUN mkdir -p /app/staticfiles /app/static /app/media \
    && mkdir -p /app/static/css /app/static/js /app/static/images

# İzinleri ayarla
RUN chmod -R 755 /app/staticfiles /app/static /app/media

# Projeyi kopyala
COPY . .

# Debug modunu kapat
ENV DEBUG=False

# Static dosyaları topla
RUN python manage.py collectstatic --noinput --clear

EXPOSE 80

# Gunicorn başlat
ENTRYPOINT ["sh", "-c", "python manage.py migrate && gunicorn core.wsgi:application --bind 0.0.0.0:80 --workers 3"]