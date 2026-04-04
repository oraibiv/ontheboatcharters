# Use an official Python runtime as a parent image

FROM python:3.12-slim
CMD ["python", "-u", "-c", "import http.server, os; port=int(os.environ.get('PORT',8080)); print(f'Listening on {port}'); http.server.HTTPServer(('0.0.0.0',port), http.server.SimpleHTTPRequestHandler).serve_forever()"]
