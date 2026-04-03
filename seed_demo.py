#!/usr/bin/env python3
"""
seed_demo.py — Populate the database with realistic demo data
Run once: python3 seed_demo.py
"""

import sqlite3
import secrets
import random
from datetime import date, timedelta, datetime
from werkzeug.security import generate_password_hash

DB_PATH = 'ontheboat.db'

# Realistic Martha's Vineyard customer names
CUSTOMERS = [
    ('Sarah Mitchell', 'sarah.mitchell@gmail.com', '(508) 555-2847'),
    ('Mike & Karen Torres', 'mtorres.family@gmail.com', '(617) 555-1923'),
    ('James Worthington III', 'jworthington@outlook.com', '(212) 555-8834'),
    ('Amy Chen', 'amychen.travels@gmail.com', '(415) 555-6612'),
    ('The Brennan Family', 'dbrennan22@yahoo.com', '(781) 555-3309'),
    ('Dave & Lisa Kowalski', 'dkowalski@gmail.com', '(508) 555-7741'),
    ('Rachel Hoffman', 'rachelhoff@icloud.com', '(617) 555-4456'),
    ('Tom Nguyen', 'tnguyen.fish@gmail.com', '(857) 555-9918'),
    ('Olivia & Mark Santos', 'osantos.mv@gmail.com', '(508) 555-5523'),
    ('Chris Blackwood', 'cblackwood@protonmail.com', '(774) 555-8802'),
    ('Jennifer Walsh', 'jwalsh.boston@gmail.com', '(617) 555-2210'),
    ('Pete Rosario', 'pete.rosario@gmail.com', '(508) 555-3367'),
    ('Sandra & Bill Hoffman', 'hoffmans.vacation@gmail.com', '(203) 555-4419'),
    ('Alex Kim', 'alexkim.photo@gmail.com', '(646) 555-7788'),
    ('Megan O\'Brien', 'megobie@gmail.com', '(508) 555-1104'),
]

SPECIAL_REQUESTS = [
    '', '', '', '', '',  # Most have none
    '', '', '',
    'Celebrating our anniversary!',
    'My son is 8 — is that ok for the offshore trip?',
    'We get seasick easily — any tips?',
    'Bringing our own rods, is that ok?',
    'Birthday surprise for my husband — can you help?',
    'Vegetarian — any snacks available?',
    'First time fishing, very excited!',
    'Will have a cooler with lunch for the group',
    'Would love to see some seals if possible',
]

def main():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    
    # Check if we already have demo data
    existing = db.execute("SELECT COUNT(*) as c FROM users WHERE role='customer'").fetchone()['c']
    if existing > 3:
        print("Demo data appears to already exist. Skipping.")
        db.close()
        return

    today = date.today()
    
    # ---------------------------------------------------------------
    # 1. Create customers
    # ---------------------------------------------------------------
    print("Creating customers...")
    customer_ids = []
    for name, email, phone in CUSTOMERS:
        try:
            db.execute(
                "INSERT INTO users (email, name, phone, password_hash, role, created_at) VALUES (?,?,?,?,?,?)",
                (email, name, phone, generate_password_hash('demo2025'), 'customer',
                 (today - timedelta(days=random.randint(5, 90))).isoformat())
            )
            cid = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()['id']
            customer_ids.append(cid)
        except sqlite3.IntegrityError:
            cid = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()['id']
            customer_ids.append(cid)
    
    print(f"  {len(customer_ids)} customers ready")

    # ---------------------------------------------------------------
    # 2. Get trip types
    # ---------------------------------------------------------------
    trips = db.execute("SELECT * FROM trip_types WHERE active=1").fetchall()
    trip_map = {t['id']: t for t in trips}
    
    # ---------------------------------------------------------------
    # 3. Create available slots — past 3 weeks + next 4 weeks
    # ---------------------------------------------------------------
    print("Creating available slots...")
    
    # Define typical schedule patterns per trip type
    trip_schedules = {}
    for t in trips:
        name = t['name'].lower()
        if 'offshore' in name:
            trip_schedules[t['id']] = {'times': ['06:00'], 'days': [1,3,5,6]}  # Mon/Wed/Fri/Sat
        elif 'sunset' in name:
            trip_schedules[t['id']] = {'times': ['17:30'], 'days': [2,4,5,6,7]}  # Tue/Thu/Fri/Sat/Sun
        elif 'tuna' in name:
            trip_schedules[t['id']] = {'times': ['05:30'], 'days': [2,4,6]}  # Tue/Thu/Sat
        elif 'cuttyhunk' in name:
            trip_schedules[t['id']] = {'times': ['09:00', '14:00'], 'days': [6,7]}  # Sat/Sun
        elif 'falmouth' in name:
            trip_schedules[t['id']] = {'times': ['08:00', '12:00', '16:00'], 'days': [1,2,3,4,5,6,7]}
        elif 'near shore' in name:
            trip_schedules[t['id']] = {'times': ['07:00', '13:00'], 'days': [1,2,3,4,5,6]}
    
    slot_ids_past = []
    slot_ids_future = []
    
    # Past slots (3 weeks back)
    for day_offset in range(-21, 0):
        d = today + timedelta(days=day_offset)
        for tid, sched in trip_schedules.items():
            if d.isoweekday() in sched['days']:
                for time in sched['times']:
                    # ~70% chance of having had the slot
                    if random.random() < 0.7:
                        trip = trip_map[tid]
                        spots = trip['max_passengers']
                        status = 'open'  # will update after bookings
                        cur = db.execute("""
                            INSERT INTO available_slots (trip_type_id, slot_date, slot_time, spots_remaining, status)
                            VALUES (?,?,?,?,?)
                        """, (tid, d.isoformat(), time, spots, status))
                        slot_ids_past.append((cur.lastrowid, tid))
    
    # Future slots (next 4 weeks)
    for day_offset in range(0, 29):
        d = today + timedelta(days=day_offset)
        for tid, sched in trip_schedules.items():
            if d.isoweekday() in sched['days']:
                for time in sched['times']:
                    if random.random() < 0.85:
                        trip = trip_map[tid]
                        spots = trip['max_passengers']
                        cur = db.execute("""
                            INSERT INTO available_slots (trip_type_id, slot_date, slot_time, spots_remaining, status)
                            VALUES (?,?,?,?,?)
                        """, (tid, d.isoformat(), time, spots, 'open'))
                        slot_ids_future.append((cur.lastrowid, tid))
    
    print(f"  {len(slot_ids_past)} past slots, {len(slot_ids_future)} future slots")

    # ---------------------------------------------------------------
    # 4. Create bookings on past slots
    # ---------------------------------------------------------------
    print("Creating past bookings...")
    booking_count = 0
    
    for slot_id, tid in slot_ids_past:
        trip = trip_map[tid]
        # 60% chance of at least one booking per past slot
        if random.random() < 0.6:
            num_bookings = random.choices([1, 2, 3], weights=[60, 30, 10])[0]
            total_booked = 0
            
            for _ in range(num_bookings):
                cust_id = random.choice(customer_ids)
                pax = random.randint(1, min(4, trip['max_passengers'] - total_booked))
                if pax <= 0:
                    break
                total_booked += pax
                
                price = trip['base_price'] * pax
                ref = f"OTB-{secrets.token_hex(4).upper()}"
                
                slot_row = db.execute("SELECT slot_date FROM available_slots WHERE id=?", (slot_id,)).fetchone()
                inv_date = slot_row['slot_date'].replace('-', '')[:8]
                inv_num = f"INV-{inv_date}-{secrets.token_hex(3).upper()}"
                
                special = random.choice(SPECIAL_REQUESTS)
                
                cur = db.execute("""
                    INSERT INTO bookings (user_id, slot_id, num_passengers, total_price, status, booking_ref, special_requests, created_at)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (cust_id, slot_id, pax, price, 'confirmed', ref, special,
                      (datetime.strptime(slot_row['slot_date'], '%Y-%m-%d') - timedelta(days=random.randint(1,14))).isoformat()))
                bid = cur.lastrowid
                
                db.execute("""
                    INSERT INTO invoices (booking_id, invoice_number, amount, status, paid_at)
                    VALUES (?,?,?,?,?)
                """, (bid, inv_num, price, 'paid', slot_row['slot_date']))
                
                booking_count += 1
            
            # Update spots remaining
            remaining = trip['max_passengers'] - total_booked
            status = 'full' if remaining <= 0 else 'open'
            db.execute("UPDATE available_slots SET spots_remaining=?, status=? WHERE id=?",
                       (max(0, remaining), status, slot_id))
    
    # ---------------------------------------------------------------
    # 5. Create some bookings on future slots (closer dates more likely)
    # ---------------------------------------------------------------
    print("Creating upcoming bookings...")
    
    for slot_id, tid in slot_ids_future:
        trip = trip_map[tid]
        slot_row = db.execute("SELECT slot_date FROM available_slots WHERE id=?", (slot_id,)).fetchone()
        days_out = (datetime.strptime(slot_row['slot_date'], '%Y-%m-%d').date() - today).days
        
        # Closer dates more likely to have bookings
        if days_out <= 3:
            book_chance = 0.7
        elif days_out <= 7:
            book_chance = 0.45
        elif days_out <= 14:
            book_chance = 0.25
        else:
            book_chance = 0.1
        
        if random.random() < book_chance:
            cust_id = random.choice(customer_ids)
            pax = random.randint(1, min(4, trip['max_passengers']))
            price = trip['base_price'] * pax
            ref = f"OTB-{secrets.token_hex(4).upper()}"
            inv_date = slot_row['slot_date'].replace('-', '')[:8]
            inv_num = f"INV-{inv_date}-{secrets.token_hex(3).upper()}"
            special = random.choice(SPECIAL_REQUESTS)
            
            cur = db.execute("""
                INSERT INTO bookings (user_id, slot_id, num_passengers, total_price, status, booking_ref, special_requests)
                VALUES (?,?,?,?,?,?,?)
            """, (cust_id, slot_id, pax, price, 'confirmed', ref, special))
            bid = cur.lastrowid
            
            db.execute("""
                INSERT INTO invoices (booking_id, invoice_number, amount, status, paid_at)
                VALUES (?,?,?,?,?)
            """, (bid, inv_num, price, 'paid', datetime.now().isoformat()))
            
            remaining = trip['max_passengers'] - pax
            status = 'full' if remaining <= 0 else 'open'
            db.execute("UPDATE available_slots SET spots_remaining=?, status=? WHERE id=?",
                       (max(0, remaining), status, slot_id))
            booking_count += 1
    
    # ---------------------------------------------------------------
    # 6. Add a couple cancelled bookings for realism
    # ---------------------------------------------------------------
    cancelled_slots = random.sample(slot_ids_past, min(3, len(slot_ids_past)))
    for slot_id, tid in cancelled_slots:
        trip = trip_map[tid]
        cust_id = random.choice(customer_ids)
        ref = f"OTB-{secrets.token_hex(4).upper()}"
        slot_row = db.execute("SELECT slot_date FROM available_slots WHERE id=?", (slot_id,)).fetchone()
        inv_date = slot_row['slot_date'].replace('-', '')[:8]
        inv_num = f"INV-{inv_date}-{secrets.token_hex(3).upper()}"
        price = trip['base_price'] * 2
        
        cur = db.execute("""
            INSERT INTO bookings (user_id, slot_id, num_passengers, total_price, status, booking_ref)
            VALUES (?,?,?,?,?,?)
        """, (cust_id, slot_id, 2, price, 'cancelled', ref))
        db.execute("""
            INSERT INTO invoices (booking_id, invoice_number, amount, status)
            VALUES (?,?,?,?)
        """, (cur.lastrowid, inv_num, price, 'void'))
    
    db.commit()
    
    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------
    total_rev = db.execute("SELECT COALESCE(SUM(amount),0) as t FROM invoices WHERE status='paid'").fetchone()['t']
    total_bookings = db.execute("SELECT COUNT(*) as c FROM bookings WHERE status='confirmed'").fetchone()['c']
    total_customers = db.execute("SELECT COUNT(*) as c FROM users WHERE role='customer'").fetchone()['c']
    
    print(f"""
  Demo Data Loaded!
  ─────────────────────────
  Customers:     {total_customers}
  Bookings:      {total_bookings} confirmed, 3 cancelled
  Season Revenue: ${total_rev:,.0f}
  Slots:         {len(slot_ids_past)} past + {len(slot_ids_future)} upcoming
  ─────────────────────────
  The dashboard should look great now.
""")
    
    db.close()


if __name__ == '__main__':
    main()
