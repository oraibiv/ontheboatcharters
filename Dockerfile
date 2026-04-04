# Use an official Python runtime as a parent image
FROM python:3.12-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

# Initialize the database
RUN python -c "from app import init_db; init_db()"

EXPOSE $PORT

CMD gunicorn -b 0.0.0.0:$PORT -w 2 --timeout 120 app:app