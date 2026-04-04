# On The Boat Charters — Project State
## As of April 3, 2026

### What This Is
A booking and management system for On The Boat Charters (www.ontheboatcharters.com), 
a charter boat business in Oak Bluffs, Martha's Vineyard run by a client of Oraibi Voumard.
The captain offers fishing charters, sunset cruises, and island shuttles.

### Current Status: LIVE on Railway
- **Live URL:** https://web-production-57241.up.railway.app/
- **GitHub repo:** https://github.com/oraibiv/ontheboatcharters
- **Railway project ID:** cf71834a-fd4a-4943-abf6-d895ac193bf7
- **Railway service ID:** e38ff9ca-b4c2-4bb5-8076-566f6a589835
- **Admin login:** admin@ontheboatcharters.com / charter2025

### Tech Stack
- **Backend:** Python 3.12 / Flask
- **Database:** SQLite (single file: ontheboat.db)
- **Deployment:** Railway via Dockerfile (NOT nixpacks)
- **Container:** python:3.12-slim, starts via `start_server.py`
- **No startCommand in railway.toml** — Dockerfile CMD handles it
- **Auto-seeds demo data** on empty database via seed_demo.py

### What's Built
1. **Customer-facing:**
   - Trip browsing page (6 trip types from current Shopify site)
   - Slot selection with date/time/price/availability
   - Customer signup/login
   - Booking flow with confirmation
   - "My Bookings" history page

2. **Admin dashboard:**
   - Revenue stats (today/week/month/season)
   - 30-day revenue bar chart (Chart.js)
   - Today's schedule with customer contact info
   - 14-day upcoming slot preview
   - Revenue breakdown by trip type

3. **Admin management pages:**
   - Slots: create single or bulk (by day-of-week over date range)
   - Bookings: view all, cancel with spot restoration
   - Customers: list sorted by total spend, detail view with history
   - Invoices: filterable by status (paid/unpaid/refunded/void)
   - Trip Types: add/edit name, price, duration, max passengers
   - Email Settings: setup instructions, test send button
   - Backup: one-click database download + JSON export

4. **Email system (mailer.py):**
   - Booking confirmation → customer
   - Cancellation notice → customer  
   - 24-hour trip reminder → customer (via send_reminders.py cron)
   - Captain daily digest → captain (via send_reminders.py cron)
   - Uses Gmail SMTP with App Password
   - NOT YET CONFIGURED — needs GMAIL_ADDRESS + GMAIL_APP_PASSWORD env vars

5. **Backup system:**
   - Admin can download .db file from dashboard (💾 Backup button)
   - Admin can export all data as JSON (📤 Export button)
   - backup.sh script for local cron-based backups
   - SQLite WAL mode for safe concurrent reads

### Trip Types (seeded from current site)
| Trip | Price | Duration | Max Pax |
|------|-------|----------|---------|
| Offshore Fishing Charter | $800 | 8 hrs | 6 |
| Sunset Cruise | $400 | 2 hrs | 10 |
| Tuna Charter | $900 | 8 hrs | 6 |
| Cuttyhunk Shuttle | $150 | 1.5 hrs | 12 |
| Falmouth Shuttle | $100 | 1 hr | 12 |
| Near Shore Fishing | $500 | 4 hrs | 6 |

### Demo Data (auto-seeded)
- 15 realistic customers
- ~138 confirmed bookings + 3 cancelled
- ~$110K season revenue
- Slots spread across past 3 weeks + next 4 weeks
- Realistic schedule patterns per trip type

### File Structure
```
ontheboat/
├── app.py                  # Main Flask app (all routes, models, logic)
├── mailer.py               # Gmail SMTP email sender + templates
├── seed_demo.py            # Demo data generator
├── send_reminders.py       # Cron script: 24hr reminders + captain digest
├── start_server.py         # Production entry point (used by Dockerfile)
├── backup.sh               # Local backup script
├── requirements.txt        # flask>=3.0, gunicorn>=22.0
├── Dockerfile              # python:3.12-slim, runs start_server.py
├── railway.toml            # Minimal: restart policy only, NO startCommand
├── Procfile                # Alternative for non-Docker deploys
├── .python-version         # 3.12
├── .gitignore              # venv, *.db, __pycache__, .env
├── README.md               # Full setup/usage docs
├── static/css/style.css    # All styles (nautical theme)
└── templates/
    ├── base.html
    ├── index.html           # Public trip listing
    ├── book.html            # Booking page
    ├── login.html
    ├── signup.html
    ├── my_bookings.html
    └── admin/
        ├── base_admin.html      # Admin layout + sidebar
        ├── dashboard.html       # Stats, charts, schedule
        ├── slots.html           # Slot management
        ├── bookings.html        # All bookings
        ├── customers.html       # Customer list
        ├── customer_detail.html # Individual customer
        ├── invoices.html        # Invoice tracking
        ├── trips.html           # Trip type management
        └── email_settings.html  # Email config + test
```

### What's NOT Done Yet
- [ ] **Railway Volume:** Need to attach volume at /data so DB persists between deploys
- [ ] **Stripe payments:** Stubbed but not wired — needs API keys + checkout flow
- [ ] **Gmail email:** Needs GMAIL_ADDRESS + GMAIL_APP_PASSWORD in Railway env vars
- [ ] **Cron for reminders:** send_reminders.py needs to be scheduled (Railway cron or external)
- [ ] **Custom domain:** Can point Cloudflare subdomain (e.g. book.ontheboatcharters.com) at Railway
- [ ] **HTTPS/SSL:** Railway handles this automatically with their domain
- [ ] **Production server:** Currently using Flask dev server; should switch to gunicorn
- [ ] **Admin password change:** Captain should change default password
- [ ] **Cancellation policy:** No self-service cancellation for customers yet

### Key Deployment Lessons Learned
1. Railway's `startCommand` in railway.toml OVERRIDES Dockerfile CMD — don't use both
2. Railway needs containers to bind to `$PORT` (or 8080 default), not hardcoded ports
3. Flask must run with `host='0.0.0.0'` and `use_reloader=False` in containers
4. `PYTHONUNBUFFERED=1` needed to see logs in Railway
5. Railway caches Docker layers aggressively — change a comment to bust cache
6. The `railway.toml` builder setting can conflict with auto-detected Dockerfiles

### Environment Variables (Railway)
Currently set:
- `SECRET_KEY` — set during initial setup
- `PYTHONUNBUFFERED` — 1

Need to add when ready:
- `GMAIL_ADDRESS` — sender Gmail
- `GMAIL_APP_PASSWORD` — Gmail app password
- `CAPTAIN_EMAIL` — where captain digest goes
- `STRIPE_PUBLIC_KEY` — when ready for payments
- `STRIPE_SECRET_KEY` — when ready for payments
