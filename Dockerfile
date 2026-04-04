# Use an official Python runtime as a parent image

FROM python:3.12-slim
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "-u", "-c", "import os; print('PORT=' + os.environ.get('PORT','NOT SET')); print('Starting...'); exec(open('app.py').read())"]