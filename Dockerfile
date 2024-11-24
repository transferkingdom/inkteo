FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV PATH="/opt/venv/bin:$PATH"
ENV DJANGO_SETTINGS_MODULE=core.settings

WORKDIR /app

RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn whitenoise

COPY . .

RUN mkdir -p /app/staticfiles /app/static /app/media \
    && chmod -R 755 /app/staticfiles /app/static /app/media

ENV DEBUG=False

RUN python -c "import django; django.setup(); from django.contrib.admin.utils import get_static_files; [print(f) for f in get_static_files()]"

RUN python manage.py collectstatic --noinput --clear

EXPOSE 80

CMD ["sh", "-c", "python manage.py migrate && gunicorn core.wsgi:application --bind 0.0.0.0:80 --workers 3"]