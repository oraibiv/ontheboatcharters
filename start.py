import os
print("=== STARTING ON THE BOAT CHARTERS ===", flush=True)
port = int(os.environ.get('PORT', 5000))
print(f"PORT = {port}", flush=True)

from app import app, init_db
print("Flask app imported", flush=True)

init_db()
print(f"Database initialized", flush=True)
print(f"Launching on 0.0.0.0:{port}", flush=True)

app.run(host='0.0.0.0', port=port, debug=False)