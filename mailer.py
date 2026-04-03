"""
mailer.py — Email notifications via Gmail SMTP
Uses App Password (not your regular Gmail password).

Setup:
  1. Go to https://myaccount.google.com/apppasswords
     (requires 2-Step Verification enabled on the Gmail account)
  2. Create an App Password for "Mail" → "Other" → name it "On The Boat"
  3. Set environment variables:
       export GMAIL_ADDRESS=yourname@gmail.com
       export GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
       export CAPTAIN_EMAIL=captain@ontheboatcharters.com  (optional, defaults to GMAIL_ADDRESS)
"""

import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

logger = logging.getLogger(__name__)

GMAIL_ADDRESS = os.environ.get('GMAIL_ADDRESS', '')
GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
CAPTAIN_EMAIL = os.environ.get('CAPTAIN_EMAIL', GMAIL_ADDRESS)
FROM_NAME = 'On The Boat Charters'


def _send_email(to_email, subject, html_body, text_body=None):
    """Send an email via Gmail SMTP. Returns True on success, False on failure."""
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        logger.warning("Email not configured — skipping send to %s: %s", to_email, subject)
        return False

    msg = MIMEMultipart('alternative')
    msg['From'] = f'{FROM_NAME} <{GMAIL_ADDRESS}>'
    msg['To'] = to_email
    msg['Subject'] = subject
    msg['Reply-To'] = CAPTAIN_EMAIL or GMAIL_ADDRESS

    if text_body:
        msg.attach(MIMEText(text_body, 'plain'))
    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=15) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        logger.info("Email sent to %s: %s", to_email, subject)
        return True
    except Exception as e:
        logger.error("Failed to send email to %s: %s", to_email, e)
        return False


# ---------------------------------------------------------------------------
# Shared HTML wrapper
# ---------------------------------------------------------------------------

def _wrap_html(content):
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0; padding:0; background:#f5f0e8; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
<div style="max-width:580px; margin:0 auto; padding:24px 16px;">

  <!-- Header -->
  <div style="background:#0b1d33; border-radius:10px 10px 0 0; padding:24px; text-align:center;">
    <span style="font-size:28px;">⚓</span>
    <h1 style="color:#fff; margin:8px 0 0; font-size:22px; font-weight:700;">On The Boat Charters</h1>
    <p style="color:rgba(255,255,255,.6); margin:4px 0 0; font-size:13px;">Martha's Vineyard</p>
  </div>

  <!-- Body -->
  <div style="background:#fff; padding:28px 24px; border-radius:0 0 10px 10px; box-shadow:0 2px 12px rgba(11,29,51,.08);">
    {content}
  </div>

  <!-- Footer -->
  <p style="text-align:center; font-size:12px; color:#999; margin-top:20px;">
    On The Boat Charters &middot; Oak Bluffs, Martha's Vineyard<br>
    <a href="https://ontheboatcharters.com" style="color:#1a6b8a;">ontheboatcharters.com</a>
  </p>

</div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# 1. Booking Confirmation — sent to customer
# ---------------------------------------------------------------------------

def send_booking_confirmation(customer_email, customer_name, booking_ref, trip_name,
                               slot_date, slot_time, num_passengers, total_price,
                               special_requests=''):
    subject = f"Booking Confirmed — {trip_name} on {slot_date}"

    requests_row = ''
    if special_requests:
        requests_row = f"""
        <tr>
          <td style="padding:8px 0; color:#6b7280; font-size:14px;">Special Requests</td>
          <td style="padding:8px 0; font-size:14px; text-align:right;">{special_requests}</td>
        </tr>"""

    content = f"""
    <h2 style="color:#0b1d33; margin:0 0 6px; font-size:20px;">You're booked, {customer_name.split()[0]}!</h2>
    <p style="color:#6b7280; margin:0 0 20px; font-size:15px;">
      We can't wait to have you aboard. Here are your booking details:
    </p>

    <div style="background:#f5f0e8; border-radius:8px; padding:16px; margin-bottom:20px;">
      <table style="width:100%; border-collapse:collapse;">
        <tr>
          <td style="padding:8px 0; color:#6b7280; font-size:14px;">Trip</td>
          <td style="padding:8px 0; font-size:14px; font-weight:700; text-align:right; color:#0b1d33;">{trip_name}</td>
        </tr>
        <tr>
          <td style="padding:8px 0; color:#6b7280; font-size:14px;">Date</td>
          <td style="padding:8px 0; font-size:14px; text-align:right;">{slot_date}</td>
        </tr>
        <tr>
          <td style="padding:8px 0; color:#6b7280; font-size:14px;">Time</td>
          <td style="padding:8px 0; font-size:14px; text-align:right;">{slot_time}</td>
        </tr>
        <tr>
          <td style="padding:8px 0; color:#6b7280; font-size:14px;">Passengers</td>
          <td style="padding:8px 0; font-size:14px; text-align:right;">{num_passengers}</td>
        </tr>
        {requests_row}
        <tr style="border-top:1px solid #e8dfd1;">
          <td style="padding:12px 0 8px; color:#0b1d33; font-size:15px; font-weight:700;">Total</td>
          <td style="padding:12px 0 8px; font-size:18px; font-weight:700; text-align:right; color:#1a6b8a;">${total_price:,.0f}</td>
        </tr>
      </table>
    </div>

    <p style="font-size:13px; color:#6b7280; margin:0 0 4px;">
      <strong>Booking Reference:</strong> {booking_ref}
    </p>
    <p style="font-size:13px; color:#6b7280; margin:0 0 16px;">
      Please save this reference — you'll need it if you contact us about your booking.
    </p>

    <div style="background:#e6f5ee; border-radius:8px; padding:14px; margin-bottom:8px;">
      <p style="margin:0; font-size:14px; color:#1a8a5c;">
        <strong>What to bring:</strong> Sunscreen, sunglasses, and a sense of adventure.
        We'll provide all the gear you need.
      </p>
    </div>
    """

    text = f"""Booking Confirmed — {trip_name}

Hi {customer_name.split()[0]},

Your trip is booked! Details:
  Trip: {trip_name}
  Date: {slot_date} at {slot_time}
  Passengers: {num_passengers}
  Total: ${total_price:,.0f}
  Ref: {booking_ref}

See you on the water!
— On The Boat Charters
"""
    return _send_email(customer_email, subject, _wrap_html(content), text)


# ---------------------------------------------------------------------------
# 2. Trip Reminder — sent to customer 24h before
# ---------------------------------------------------------------------------

def send_trip_reminder(customer_email, customer_name, trip_name, slot_date, slot_time, num_passengers):
    subject = f"Reminder: {trip_name} tomorrow at {slot_time}"

    content = f"""
    <h2 style="color:#0b1d33; margin:0 0 6px; font-size:20px;">See you tomorrow, {customer_name.split()[0]}!</h2>
    <p style="color:#6b7280; margin:0 0 20px; font-size:15px;">
      Just a friendly reminder — your trip is coming up:
    </p>

    <div style="background:#d5eef7; border-radius:8px; padding:18px; text-align:center; margin-bottom:20px;">
      <p style="margin:0; font-size:22px; font-weight:700; color:#0b1d33;">{trip_name}</p>
      <p style="margin:6px 0 0; font-size:16px; color:#1a6b8a;">
        {slot_date} at {slot_time} &middot; {num_passengers} passenger{'s' if num_passengers != 1 else ''}
      </p>
    </div>

    <h3 style="color:#0b1d33; font-size:15px; margin:0 0 8px;">Quick Checklist</h3>
    <p style="font-size:14px; color:#444; line-height:1.7; margin:0 0 16px;">
      ☑ Sunscreen &amp; sunglasses<br>
      ☑ Light layers (it's cooler on the water)<br>
      ☑ Motion sickness meds if you're prone<br>
      ☑ Camera for the catches &amp; views<br>
      ☑ Valid ID for each passenger
    </p>

    <p style="font-size:14px; color:#6b7280; margin:0;">
      Questions? Reply to this email and we'll get right back to you.
    </p>
    """

    text = f"""Reminder: {trip_name} Tomorrow!

Hi {customer_name.split()[0]},

Your trip is tomorrow:
  {trip_name}
  {slot_date} at {slot_time}
  {num_passengers} passenger{'s' if num_passengers != 1 else ''}

Don't forget sunscreen & sunglasses!

— On The Boat Charters
"""
    return _send_email(customer_email, subject, _wrap_html(content), text)


# ---------------------------------------------------------------------------
# 3. Cancellation Notice — sent to customer
# ---------------------------------------------------------------------------

def send_cancellation_notice(customer_email, customer_name, booking_ref, trip_name, slot_date, slot_time):
    subject = f"Booking Cancelled — {booking_ref}"

    content = f"""
    <h2 style="color:#0b1d33; margin:0 0 6px; font-size:20px;">Booking Cancelled</h2>
    <p style="color:#6b7280; margin:0 0 20px; font-size:15px;">
      Hi {customer_name.split()[0]}, your booking has been cancelled:
    </p>

    <div style="background:#fbeae8; border-radius:8px; padding:16px; margin-bottom:20px;">
      <table style="width:100%; border-collapse:collapse;">
        <tr>
          <td style="padding:6px 0; color:#6b7280; font-size:14px;">Trip</td>
          <td style="padding:6px 0; font-size:14px; text-align:right;">{trip_name}</td>
        </tr>
        <tr>
          <td style="padding:6px 0; color:#6b7280; font-size:14px;">Date</td>
          <td style="padding:6px 0; font-size:14px; text-align:right;">{slot_date} at {slot_time}</td>
        </tr>
        <tr>
          <td style="padding:6px 0; color:#6b7280; font-size:14px;">Reference</td>
          <td style="padding:6px 0; font-size:14px; text-align:right;">{booking_ref}</td>
        </tr>
      </table>
    </div>

    <p style="font-size:14px; color:#6b7280; margin:0;">
      If you have questions about your refund or want to rebook, just reply to this email.
    </p>
    """

    text = f"""Booking Cancelled

Hi {customer_name.split()[0]},

Your booking {booking_ref} for {trip_name} on {slot_date} at {slot_time} has been cancelled.

Questions? Reply to this email.

— On The Boat Charters
"""
    return _send_email(customer_email, subject, _wrap_html(content), text)


# ---------------------------------------------------------------------------
# 4. Captain Daily Digest — sent to captain each morning
# ---------------------------------------------------------------------------

def send_captain_digest(bookings_today, bookings_tomorrow, revenue_week):
    """
    bookings_today / bookings_tomorrow: list of dicts with keys:
      slot_time, trip_name, customer_name, customer_phone, customer_email,
      num_passengers, special_requests
    revenue_week: float
    """
    if not CAPTAIN_EMAIL:
        return False

    today_str = datetime.now().strftime('%A, %B %d')
    subject = f"Daily Schedule — {today_str}"

    def _booking_rows(bookings):
        if not bookings:
            return '<tr><td colspan="4" style="padding:12px; color:#999; text-align:center; font-size:14px;">No trips scheduled</td></tr>'
        rows = ''
        for b in bookings:
            phone = b.get('customer_phone') or '—'
            notes = f'<br><em style="color:#d4a017; font-size:12px;">{b["special_requests"]}</em>' if b.get('special_requests') else ''
            rows += f"""
            <tr>
              <td style="padding:8px; border-bottom:1px solid #f0f0f0; font-weight:700; color:#1a6b8a;">{b['slot_time']}</td>
              <td style="padding:8px; border-bottom:1px solid #f0f0f0;">{b['trip_name']}</td>
              <td style="padding:8px; border-bottom:1px solid #f0f0f0;">
                {b['customer_name']} ({b['num_passengers']} pax)<br>
                <span style="font-size:12px; color:#6b7280;">{phone} &middot; {b['customer_email']}</span>
                {notes}
              </td>
            </tr>"""
        return rows

    content = f"""
    <h2 style="color:#0b1d33; margin:0 0 16px; font-size:20px;">Good morning, Captain</h2>

    <p style="margin:0 0 4px; font-size:13px; color:#6b7280; text-transform:uppercase; letter-spacing:.05em; font-weight:600;">This Week's Revenue</p>
    <p style="margin:0 0 20px; font-size:28px; font-weight:700; color:#1a6b8a;">${revenue_week:,.0f}</p>

    <h3 style="color:#0b1d33; font-size:16px; margin:0 0 8px;">Today — {today_str}</h3>
    <table style="width:100%; border-collapse:collapse; margin-bottom:24px;">
      {_booking_rows(bookings_today)}
    </table>

    <h3 style="color:#0b1d33; font-size:16px; margin:0 0 8px;">Tomorrow</h3>
    <table style="width:100%; border-collapse:collapse;">
      {_booking_rows(bookings_tomorrow)}
    </table>
    """

    text_lines = [f"Daily Schedule — {today_str}", "", f"Week Revenue: ${revenue_week:,.0f}", "", "TODAY:"]
    for b in bookings_today:
        text_lines.append(f"  {b['slot_time']} — {b['trip_name']} — {b['customer_name']} ({b['num_passengers']} pax) — {b.get('customer_phone', '')}")
    if not bookings_today:
        text_lines.append("  No trips today")
    text_lines.append("")
    text_lines.append("TOMORROW:")
    for b in bookings_tomorrow:
        text_lines.append(f"  {b['slot_time']} — {b['trip_name']} — {b['customer_name']} ({b['num_passengers']} pax) — {b.get('customer_phone', '')}")
    if not bookings_tomorrow:
        text_lines.append("  No trips tomorrow")

    return _send_email(CAPTAIN_EMAIL, subject, _wrap_html(content), '\n'.join(text_lines))
