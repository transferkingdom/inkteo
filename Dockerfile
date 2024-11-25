FROM python:3.11-slim

WORKDIR /app

# Gerekli paketleri yükle
RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Python paketlerini yükle
COPY requirements.txt .
RUN pip install -r requirements.txt gunicorn

# Projeyi kopyala
COPY . .

# Easypanel volume dizinini oluştur
RUN mkdir -p /etc/easypanel/projects/inkteo/inkteo/volumes/static \
    && chmod -R 755 /etc/easypanel/projects/inkteo/inkteo/volumes/static

EXPOSE 80

# Volume mount noktası
VOLUME ["/etc/easypanel/projects/inkteo/inkteo/volumes/static"]

CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn core.wsgi:application --bind 0.0.0.0:80 --workers 3"]