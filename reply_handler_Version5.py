import imaplib
import email
import email.header
import smtplib
import re
import sqlite3
import random
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import time
import email.utils

# Email configuration
EMAIL = "zuberipersonal@gmail.com"
PASSWORD = "lavfqbdauszbjuxp"
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

# Database configuration
DB_PATH = r"E:\BSAI-5th\DataMining\Real_State_Automation\real_estate.db"

# Real estate office locations in Islamabad
OFFICE_LOCATIONS = [
    {
        "name": "Premier Properties Islamabad",
        "address": "Office #304, 3rd Floor, Emaar Business Complex, F-8 Markaz, Islamabad",
        "google_maps": "https://maps.app.goo.gl/V5wqJh7XkKZeBsry8",
        "phone": "+923197757134"
    },
    {
        "name": "Blue World Real Estate",
        "address": "Office #12, Ghauri Plaza, Jinnah Avenue, Blue Area, Islamabad",
        "google_maps": "https://maps.app.goo.gl/Z3HRs2kJpQEd5NSSA",
        "phone": "+923197757134"
    },
    {
        "name": "Capital Smart Properties",
        "address": "Suite #5, First Floor, Kohistan Plaza, F-10 Markaz, Islamabad",
        "google_maps": "https://maps.app.goo.gl/LnX8ArdK8sZAy3q78",
        "phone": "+923197757134"
    }
]

# Available time slots for meetings (9 AM to 5 PM, Monday-Saturday)
MEETING_HOURS = [f"{h}:00" for h in range(9, 18)]
MEETING_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


class EmailResponseHandler:
    def __init__(self):
        """Initialize the email response handler"""
        self.conn = self.connect_to_db()

    def connect_to_db(self):
        """Connect to the database"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def safe_get(self, row, column, default=None):
        """Safely get a column value from a sqlite Row object with a default value if missing"""
        try:
            return row[column] if column in row.keys() else default
        except (IndexError, TypeError):
            return default

    def check_email_replies(self):
        """Check email inbox for replies from clients in the last 10 minutes"""
        print(f"\n{'=' * 60}\nChecking for email replies from the last 10 minutes...")

        try:
            # Connect to IMAP server
            mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            mail.login(EMAIL, PASSWORD)
            mail.select('inbox')

            # Calculate time 10 minutes ago
            ten_minutes_ago = (datetime.now() - timedelta(minutes=10))
            date_string = ten_minutes_ago.strftime("%d-%b-%Y")

            # Search for all emails from the last 10 minutes
            # Note: IMAP's SINCE includes the specified date but we'll filter more precisely later
            status, data = mail.search(None, f'SINCE "{date_string}"')

            if status != 'OK':
                print("Error searching for emails")
                return

            email_ids = data[0].split()

            if not email_ids:
                print("No new replies found in the last 10 minutes")
                return

            print(f"Found {len(email_ids)} emails since {date_string}. Processing...")
            recent_emails = 0

            # Process each email
            for email_id in email_ids:
                status, data = mail.fetch(email_id, '(RFC822)')

                if status != 'OK':
                    print(f"Error fetching email {email_id}")
                    continue

                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Check if this email is from the last 10 minutes
                date_tuple = email.utils.parsedate_tz(msg['Date'])
                if date_tuple:
                    email_time = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
                    if email_time < ten_minutes_ago:
                        # Skip emails older than 10 minutes
                        continue

                    recent_emails += 1

                # Get email details
                subject = self.decode_header(msg['subject'])
                from_address = self.parse_from_address(msg['from'])
                body = self.get_email_body(msg)

                print(f"\nProcessing email from: {from_address}")
                print(f"Subject: {subject}")
                print(f"Time: {email_time.strftime('%Y-%m-%d %H:%M:%S')}")

                # Check if client exists in database
                client = self.get_client_by_email(from_address)

                if client:
                    print(f"Matched to client: {client['name']} (ID: {client['id']})")

                    # Check if the reply indicates interest
                    if self.is_interested(body, subject):
                        print(f"✅ Client shows interest! Scheduling meeting...")

                        # Schedule meeting and send follow-up
                        self.handle_interested_client(client, subject, body)
                    else:
                        print(f"❌ No clear interest detected. Marking as reviewed.")
                else:
                    print(f"⚠️ Email from {from_address} not matched to any client in database")

            # Summary
            print(f"\nProcessed {recent_emails} emails from the last 10 minutes")

            # Close connection
            mail.logout()

        except Exception as e:
            print(f"Error checking email replies: {e}")

    def decode_header(self, header):
        """Decode email header"""
        if not header:
            return ""

        decoded_header, encoding = email.header.decode_header(header)[0]

        if isinstance(decoded_header, bytes):
            return decoded_header.decode(encoding if encoding else 'utf-8', errors='replace')
        return decoded_header

    def parse_from_address(self, from_header):
        """Extract email address from From header"""
        if not from_header:
            return ""

        # Try to extract email with regex
        email_match = re.search(r'<([^<>]+)>', from_header)

        if email_match:
            return email_match.group(1).lower()
        else:
            # If no angle brackets, try to extract raw email
            email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', from_header)
            if email_match:
                return email_match.group(1).lower()
        return from_header.lower()

    def get_email_body(self, msg):
        """Extract email body text"""
        body = ""

        if msg.is_multipart():
            # Handle multipart messages
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == "text/plain":
                    try:
                        charset = part.get_content_charset() or 'utf-8'
                        body += part.get_payload(decode=True).decode(charset, errors='replace')
                    except Exception as e:
                        print(f"Error decoding email body: {e}")
        else:
            # Handle single part messages
            try:
                charset = msg.get_content_charset() or 'utf-8'
                body = msg.get_payload(decode=True).decode(charset, errors='replace')
            except Exception as e:
                print(f"Error decoding email body: {e}")

        return body

    def get_client_by_email(self, email_address):
        """Find client by email address"""
        cursor = self.conn.cursor()

        cursor.execute("SELECT * FROM clients_data WHERE email = ?", (email_address,))
        client = cursor.fetchone()

        return client

    def is_interested(self, body, subject):
        """Determine if the client is interested based on email content"""
        # Convert to lowercase for case-insensitive matching
        body_text = body.lower()
        subject_text = subject.lower()

        # Keywords indicating interest
        interest_keywords = [
            'interested', 'interest', 'like to see', 'would like to', 'want to see',
            'visit', 'viewing', 'look at', 'check', 'schedule', 'appointment', 'meeting',
            'more information', 'more details', 'contact', 'call me', 'price', 'available',
            'when can i', 'possible', 'please send', 'yes', 'tell me more', 'address',
            'location', 'further information', 'inspection', 'property tour', 'details'
        ]

        # Check for interest keywords
        for keyword in interest_keywords:
            if keyword in body_text or keyword in subject_text:
                return True

        return False

    def handle_interested_client(self, client, subject, body):
        """Handle an interested client: schedule meeting and send follow-up"""
        # 1. Get the client's property matches
        matches = self.get_client_matches(client['id'])

        if not matches:
            print(f"No property matches found for client {client['name']}")
            return

        # 2. Schedule a meeting
        meeting_info = self.schedule_meeting()

        # 3. Log the meeting in database
        meeting_id = self.log_meeting(client['id'], meeting_info)

        # 4. Send follow-up email with meeting details
        self.send_meeting_confirmation(client, matches, meeting_info)

        # 5. Update client status
        self.update_client_status(client['id'], "meeting_scheduled")

        print(f"Meeting scheduled for {client['name']} on {meeting_info['date']} at {meeting_info['time']}")

    def get_client_matches(self, client_id):
        """Get property matches for a client"""
        cursor = self.conn.cursor()

        # Join match_notifications and property_leads to get full property details
        cursor.execute("""
            SELECT p.*, m.match_score 
            FROM match_notifications m
            JOIN property_leads p ON m.property_id = p.id
            WHERE m.client_id = ?
            ORDER BY m.match_score DESC
        """, (client_id,))

        matches = cursor.fetchall()
        return matches

    def schedule_meeting(self):
        """Schedule a meeting time and select an office location"""
        # Select a random office location
        office = random.choice(OFFICE_LOCATIONS)

        # Generate a meeting date (between 2-7 days from now)
        days_ahead = random.randint(2, 7)
        meeting_date = (datetime.now() + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

        # Select a day of week
        day_of_week = MEETING_DAYS[random.randint(0, len(MEETING_DAYS) - 1)]

        # Select a meeting time
        meeting_time = MEETING_HOURS[random.randint(0, len(MEETING_HOURS) - 1)]

        return {
            "office": office,
            "date": meeting_date,
            "day": day_of_week,
            "time": meeting_time
        }

    def log_meeting(self, client_id, meeting_info):
        """Log the scheduled meeting in the database"""
        cursor = self.conn.cursor()

        # Create meetings table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scheduled_meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                meeting_date TEXT,
                meeting_time TEXT,
                office_name TEXT,
                office_address TEXT,
                status TEXT DEFAULT 'scheduled',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients_data (id)
            )
        ''')

        # Insert meeting record
        cursor.execute('''
            INSERT INTO scheduled_meetings 
            (client_id, meeting_date, meeting_time, office_name, office_address, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            client_id,
            meeting_info['date'],
            meeting_info['time'],
            meeting_info['office']['name'],
            meeting_info['office']['address'],
            'scheduled'
        ))

        self.conn.commit()
        return cursor.lastrowid

    def update_client_status(self, client_id, status):
        """Update client status in the database"""
        cursor = self.conn.cursor()

        cursor.execute("UPDATE clients_data SET status = ? WHERE id = ?", (status, client_id))
        self.conn.commit()

    def send_meeting_confirmation(self, client, matches, meeting_info):
        """Send meeting confirmation email to the client"""
        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Your Property Viewing Appointment - {meeting_info['date']}"
        msg['From'] = EMAIL
        msg['To'] = client['email']

        # Pick top 3 matches to highlight
        top_matches = matches[:3] if len(matches) >= 3 else matches

        # Create HTML content with meeting details and property information
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Property Viewing Appointment</title>
            <style>
                body {{
                    font-family: 'Segoe UI', Arial, sans-serif;
                    line-height: 1.6;
                    color: #333333;
                    margin: 0;
                    padding: 0;
                    background-color: #f9f9f9;
                }}
                .container {{
                    max-width: 650px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #ffffff;
                    border-radius: 8px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.05);
                }}
                .header {{
                    background-color: #0a6eb4;
                    color: white;
                    padding: 20px;
                    text-align: center;
                    border-radius: 8px 8px 0 0;
                    margin-bottom: 20px;
                }}
                .footer {{
                    background-color: #f5f5f5;
                    padding: 15px;
                    text-align: center;
                    font-size: 12px;
                    color: #666;
                    border-radius: 0 0 8px 8px;
                    margin-top: 20px;
                }}
                .meeting-box {{
                    background-color: #f8f9fa;
                    border-left: 4px solid #28a745;
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
                .meeting-title {{
                    color: #28a745;
                    font-size: 18px;
                    font-weight: bold;
                    margin-bottom: 10px;
                }}
                .meeting-detail {{
                    margin: 5px 0;
                }}
                .property {{
                    margin-bottom: 15px;
                    padding: 10px;
                    border: 1px solid #e0e0e0;
                    border-radius: 5px;
                }}
                .property-title {{
                    font-size: 16px;
                    font-weight: bold;
                    color: #0a6eb4;
                }}
                .property-price {{
                    font-weight: bold;
                    color: #28a745;
                }}
                .map-link {{
                    display: inline-block;
                    margin-top: 10px;
                    color: white;
                    background-color: #0a6eb4;
                    padding: 8px 15px;
                    text-decoration: none;
                    border-radius: 4px;
                    font-weight: bold;
                }}
                .highlight {{
                    background-color: #fffde7;
                    padding: 2px 4px;
                    border-radius: 3px;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Your Property Viewing Appointment</h1>
                    <p>We're excited to meet with you!</p>
                </div>

                <p>Dear {client['name']},</p>

                <p>Thank you for your interest in the properties we shared with you. We're delighted to confirm your property consultation appointment:</p>

                <div class="meeting-box">
                    <div class="meeting-title">Appointment Details</div>

                    <p class="meeting-detail"><strong>Date:</strong> {meeting_info['date']} ({meeting_info['day']})</p>
                    <p class="meeting-detail"><strong>Time:</strong> {meeting_info['time']}</p>
                    <p class="meeting-detail"><strong>Location:</strong> {meeting_info['office']['name']}</p>
                    <p class="meeting-detail"><strong>Address:</strong> {meeting_info['office']['address']}</p>
                    <p class="meeting-detail"><strong>Contact Number:</strong> {meeting_info['office']['phone']}</p>

                    <a href="{meeting_info['office']['google_maps']}" class="map-link" target="_blank">View Map Location</a>
                </div>

                <p>During this meeting, our property consultant will:</p>

                <ul>
                    <li>Discuss your property requirements in detail</li>
                    <li>Share complete information about the properties you're interested in</li>
                    <li>Answer all your questions about pricing, documentation, and legalities</li>
                    <li>Arrange property visits based on your preferences</li>
                    <li>Provide guidance on negotiation and purchasing process</li>
                </ul>

                <p>The following properties will be discussed during the meeting:</p>

                <div class="properties">
        """

        # Add top matches with FIXED .get() ISSUE
        for match in top_matches:
            # Use safe access for these fields with fallback values
            contact_number = match['contact_number'] if 'contact_number' in match.keys() else 'Available at meeting'
            contact_email = match['contact_email'] if 'contact_email' in match.keys() else 'Available at meeting'

            html += f"""
                <div class="property">
                    <div class="property-title">{match['title']}</div>
                    <div class="property-price">{match['price']}</div>
                    <p><strong>Location:</strong> {match['location']}</p>
                    <p><strong>Size:</strong> {match['size']}</p>
                </div>
            """

        html += f"""
                </div>

                <p>Please bring any relevant documents or information that might help us better understand your requirements.</p>

                <p>If you need to reschedule or have any questions before the meeting, please contact us at {EMAIL} or call us at {meeting_info['office']['phone']}.</p>

                <p>We're looking forward to meeting you and helping you find your perfect property!</p>

                <p>Best regards,<br>
                <strong>The Premier Property Team</strong><br>
                {meeting_info['office']['name']}</p>

                <div class="footer">
                    <p>This appointment was scheduled based on your expressed interest in our property listings.</p>
                    <p>© 2025 Premier Property Consultants. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Attach HTML content
        msg.attach(MIMEText(html, 'html'))

        # Send email
        try:
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
                server.login(EMAIL, PASSWORD)
                server.sendmail(EMAIL, client['email'], msg.as_string())

            print(f"✅ Meeting confirmation email sent to {client['name']} ({client['email']})")
            return True
        except Exception as e:
            print(f"❌ Failed to send meeting confirmation email to {client['email']}: {e}")
            return False

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


def main():
    print("=" * 80)
    print("Email Response Handler and Meeting Scheduler")
    print("=" * 80)
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    handler = EmailResponseHandler()

    try:
        # Check for email replies
        handler.check_email_replies()

    except Exception as e:
        print(f"Error running email response handler: {e}")

    finally:
        handler.close()

    print("\nProcess completed.")


if __name__ == "__main__":
    main()