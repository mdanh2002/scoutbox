FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DEBIAN_FRONTEND=noninteractive
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates netcat-openbsd libreoffice-writer libreoffice-core fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt
COPY . /app/
RUN chmod +x /app/entrypoint.sh && mkdir -p /app/media /app/staticfiles
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn","opportunity_portal.wsgi:application","--bind","0.0.0.0:8000","--workers","2","--threads","4","--timeout","120"]
