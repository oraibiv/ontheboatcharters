import os, sys
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

port = int(os.environ.get('PORT', 8080))
print(f"Starting On The Boat Charters on port {port}")

from app import app, init_db
init_db()
app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
