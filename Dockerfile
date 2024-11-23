FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install gunicorn

COPY . .

RUN mkdir -p /app/staticfiles /app/media
RUN python manage.py collectstatic --noinput --clear

EXPOSE 80

CMD ["gunicorn", "--bind", "0.0.0.0:80", "core.wsgi:application"]