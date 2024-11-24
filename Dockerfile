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

# Virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn whitenoise

# Proje kopyalanmadan önce dizinleri oluştur
RUN mkdir -p /app/static /app/media /app/staticfiles
RUN chmod -R 777 /app/static /app/media /app/staticfiles

# Projeyi kopyala
COPY . .

# Static dosyaları topla
RUN DJANGO_SETTINGS_MODULE=core.settings python manage.py collectstatic --noinput --clear

EXPOSE 80

CMD ["gunicorn", "core.wsgi:application", "--bind", "0.0.0.0:80", "--workers", "3"]