# On The Boat Charters — Booking & Management System

A self-contained booking system for On The Boat Charters (Martha's Vineyard).  
Customers can browse trips, pick available dates, and book. The captain gets a 
full admin dashboard with scheduling, customer database, invoices, and revenue insights.

## Quick Start

```bash
# 1. Install dependencies (Python 3.10+)
pip install -r requirements.txt

# 2. Run the app
python app.py

# 3. Open your browser
#    Public site:   http://localhost:5000
#    Admin login:   http://localhost:5000/login
#      Email:       admin@ontheboatcharters.com
#      Password:    charter2025
```

The database (`ontheboat.db`) is created automatically on first run,  
pre-loaded with the 6 trip types from the current website.

## How It Works

### For the Captain (Admin)

1. **Log in** at `/login` with the admin credentials above
2. **Create available slots** — go to Slots, pick a trip type, set the date/time.  
   You can bulk-create slots (e.g. "Sunset Cruise every Fri/Sat from June–August").
3. **View the dashboard** — see today's schedule, upcoming bookings, revenue stats,  
   and a 30-day revenue chart.
4. **Manage everything** — customers, bookings, invoices, and trip types all have  
   their own pages in the admin sidebar.

### For Customers

1. Browse available trips on the homepage
2. Click a trip to see available dates
3. Sign up / log in, pick a slot, confirm booking
4. View booking history at "My Bookings"

## Database & Backups

The entire database is a single SQLite file: `ontheboat.db`

```bash
# Back up manually
chmod +x backup.sh
./backup.sh

# Set up daily automated backups (cron)
crontab -e
# Add this line:
0 3 * * * cd /path/to/ontheboat && ./backup.sh
```

Backups go to `./backups/` and auto-clean to keep the last 30.

## Project Structure

```
ontheboat/
├── app.py                  # Main application (routes, models, logic)
├── requirements.txt        # Python dependencies
├── backup.sh              # Database backup script
├── ontheboat.db           # SQLite database (created on first run)
├── static/
│   └── css/
│       └── style.css      # All styles
└── templates/
    ├── base.html           # Shared layout
    ├── index.html          # Public trip listing
    ├── book.html           # Booking page with slot selection
    ├── login.html          # Login
    ├── signup.html         # Registration
    ├── my_bookings.html    # Customer booking history
    └── admin/
        ├── base_admin.html     # Admin layout with sidebar
        ├── dashboard.html      # Stats, schedule, revenue chart
        ├── slots.html          # Create & manage available slots
        ├── bookings.html       # All bookings
        ├── customers.html      # Customer list
        ├── customer_detail.html# Individual customer view
        ├── invoices.html       # Invoice tracking with filters
        └── trips.html          # Trip type management
```

## Adding Stripe Payments (When Ready)

The app is structured to plug in Stripe. When you're ready:

1. Get your Stripe keys from https://dashboard.stripe.com
2. Set environment variables:
   ```bash
   export STRIPE_PUBLIC_KEY=pk_live_...
   export STRIPE_SECRET_KEY=sk_live_...
   ```
3. Install the Stripe library: `pip install stripe`
4. The booking confirmation flow already has the right structure —  
   you'd add a Stripe Checkout session before creating the booking record.

## Deploying Later

This runs anywhere Python runs. Easy options:

- **Railway / Render** — push the folder, set `python app.py` as the start command
- **VPS (DigitalOcean, etc.)** — use gunicorn: `pip install gunicorn && gunicorn app:app`
- **For production**, change `SECRET_KEY` to a fixed random value and turn off debug mode

## Changing the Admin Password

Log in, or run this in Python:
```python
from werkzeug.security import generate_password_hash
import sqlite3
db = sqlite3.connect('ontheboat.db')
db.execute("UPDATE users SET password_hash=? WHERE email='admin@ontheboatcharters.com'",
           (generate_password_hash('your-new-password'),))
db.commit()
```
