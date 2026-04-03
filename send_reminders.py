#!/usr/bin/env python3
"""
send_reminders.py — Scheduled email tasks for On The Boat Charters

Run this once daily (ideally 6 AM) via cron:
    0 6 * * * cd /path/to/ontheboat && /path/to/venv/bin/python send_reminders.py

What it does:
  1. Sends 24-hour trip reminders to customers with bookings tomorrow
  2. Sends the captain a daily digest (today's schedule + tomorrow preview + weekly revenue)
"""

import sqlite3
import os
import sys
from datetime import date, timedelta
from mailer import send_trip_reminder, send_captain_digest

DB_PATH = os.environ.get('DATABASE', 'ontheboat.db')


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def send_customer_reminders(db, tomorrow):
    """Send reminder emails to customers with bookings tomorrow."""
    bookings = db.execute("""
        SELECT b.*, s.slot_date, s.slot_time, t.name as trip_name,
               u.name as customer_name, u.email as customer_email
        FROM bookings b
        JOIN available_slots s ON b.slot_id = s.id
        JOIN trip_types t ON s.trip_type_id = t.id
        JOIN users u ON b.user_id = u.id
        WHERE s.slot_date = ? AND b.status = 'confirmed'
    """, (tomorrow.isoformat(),)).fetchall()

    sent = 0
    for b in bookings:
        ok = send_trip_reminder(
            customer_email=b['customer_email'],
            customer_name=b['customer_name'],
            trip_name=b['trip_name'],
            slot_date=b['slot_date'],
            slot_time=b['slot_time'],
            num_passengers=b['num_passengers'],
        )
        if ok:
            sent += 1

    print(f"  Reminders: {sent}/{len(bookings)} sent for {tomorrow}")
    return sent


def send_daily_digest(db, today, tomorrow):
    """Send the captain a morning digest."""

    def _fetch_schedule(target_date):
        return [dict(row) for row in db.execute("""
            SELECT s.slot_time, t.name as trip_name,
                   u.name as customer_name, u.phone as customer_phone,
                   u.email as customer_email, b.num_passengers, b.special_requests
            FROM bookings b
            JOIN available_slots s ON b.slot_id = s.id
            JOIN trip_types t ON s.trip_type_id = t.id
            JOIN users u ON b.user_id = u.id
            WHERE s.slot_date = ? AND b.status = 'confirmed'
            ORDER BY s.slot_time
        """, (target_date.isoformat(),)).fetchall()]

    bookings_today = _fetch_schedule(today)
    bookings_tomorrow = _fetch_schedule(tomorrow)

    revenue_week = db.execute("""
        SELECT COALESCE(SUM(i.amount), 0) as total
        FROM invoices i
        JOIN bookings b ON i.booking_id = b.id
        JOIN available_slots s ON b.slot_id = s.id
        WHERE i.status = 'paid'
          AND s.slot_date >= date(?, '-7 days')
          AND s.slot_date <= ?
    """, (today.isoformat(), today.isoformat())).fetchone()['total']

    ok = send_captain_digest(bookings_today, bookings_tomorrow, revenue_week)
    print(f"  Captain digest: {'sent' if ok else 'skipped (email not configured)'}")
    return ok


def main():
    print(f"On The Boat — Daily Email Tasks")
    print(f"{'=' * 40}")

    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        sys.exit(1)

    db = get_db()
    today = date.today()
    tomorrow = today + timedelta(days=1)

    print(f"  Today:    {today}")
    print(f"  Tomorrow: {tomorrow}")
    print()

    send_customer_reminders(db, tomorrow)
    send_daily_digest(db, today, tomorrow)

    db.close()
    print("\nDone.")


if __name__ == '__main__':
    main()
