# Use an official Python runtime as a parent image

FROM python:3.12-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

RUN python -c "from app import init_db; init_db()"

CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT:-8080} -w 2 --timeout 120 app:app"]