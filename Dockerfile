# Образ приложения HelpDesk.
# Сборка: docker build -t helpdesk .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/data/requests.db

WORKDIR /app

# Сначала только зависимости: при изменении кода этот слой берётся из кеша и сборка идёт быстрее
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Приложение работает не от root. База лежит в /data, туда подключается том
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data \
    && chown appuser:appuser /data
USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=4).status == 200 else 1)"

CMD ["waitress-serve", "--host=0.0.0.0", "--port=5000", "--threads=8", "--call", "app:create_app"]
