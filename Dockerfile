FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN echo "=== requirements.txt ===" \
    && cat /app/requirements.txt \
    && echo "=== instalando dependencias ===" \
    && python -m pip install --no-cache-dir -r /app/requirements.txt \
    && python -m pip check \
    && python -c "import fastapi, uvicorn, sqlalchemy, psycopg, jinja2, resend, pywebpush, multipart; print('DEPENDENCIAS OK'); print('uvicorn', uvicorn.__version__); print('psycopg', psycopg.__version__)"

COPY . /app

CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --proxy-headers --forwarded-allow-ips='*'"]
