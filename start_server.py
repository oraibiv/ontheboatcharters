import os, sys
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

port = int(os.environ.get('PORT', 8080))
print(f"Starting On The Boat Charters on port {port}")

from app import app, init_db
init_db()
print("Database initialized")

# Auto-seed demo data if database is empty
import sqlite3
db_path = app.config['DATABASE']
print(f"Database path: {db_path}")

db = sqlite3.connect(db_path)
customer_count = db.execute("SELECT COUNT(*) FROM users WHERE role='customer'").fetchone()[0]
db.close()

if customer_count == 0:
    print("Empty database — seeding demo data...")
    os.environ['DATABASE'] = db_path
    import seed_demo
    seed_demo.DB_PATH = db_path
    seed_demo.main()
    print("Demo data loaded!")
else:
    print(f"Database has {customer_count} customers, skipping seed.")

app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
