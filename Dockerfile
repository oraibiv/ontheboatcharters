# Use an official Python runtime as a parent image

FROM python:3.12-slim
WORKDIR /app
COPY . /app
CMD ["sh", "-c", "echo 'Files in /app:' && ls -la /app && echo '---' && python -u -c \"import http.server,os; port=int(os.environ.get('PORT',8080)); print('Listening on '+str(port)); http.server.HTTPServer(('0.0.0.0',port), http.server.SimpleHTTPRequestHandler).serve_forever()\""]
