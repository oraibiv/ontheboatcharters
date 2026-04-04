import os, sys
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

port = int(os.environ.get('PORT', 8080))
print(f"=== STARTING === PORT={port}", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"CWD: {os.getcwd()}", flush=True)
print(f"Files: {os.listdir('.')}", flush=True)

from app import app, init_db
print("Flask imported OK", flush=True)

init_db()
print(f"DB ready, launching on 0.0.0.0:{port}", flush=True)

app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)