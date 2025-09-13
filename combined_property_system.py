import sqlite3
import re
import smtplib
import imaplib
import email
import email.header
import email.utils
import random
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
import threading

# Email configuration
EMAIL = "zuberipersonal@gmail.com"
PASSWORD = "lavfqbdauszbjuxp"
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

# Database configuration
DB_PATH = r"E:\BSAI-5th\DataMining\Real_State_Automation\real_estate.db"

# Meeting configuration
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

# Meeting time slots
MEETING_HOURS = [f"{h}:00" for h in range(9, 18)]
MEETING_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

# Processing intervals (in seconds)
PROPERTY_MATCH_INTERVAL = 3600  # Run property matching every hour
REPLY_CHECK_INTERVAL = 300  # Check for replies every 5 minutes


class CombinedPropertySystem:
    def __init__(self):
        """Initialize the combined property matching and reply handling system"""
        print(f"Initializing Combined Property System at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        self.conn = self.connect_to_db()
        self.last_property_match_time = datetime.now() - timedelta(hours=1)  # Run match on first execution

    def connect_to_db(self):
        """Connect to the database"""
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def refresh_db_connection(self):
        """Refresh database connection if needed"""
        try:
            # Test if connection is still working
            self.conn.execute("SELECT 1")
        except (sqlite3.OperationalError, sqlite3.ProgrammingError):
            # Reconnect if there's an issue
            print("Refreshing database connection...")
            self.conn = self.connect_to_db()
        return self.conn

    def run(self):
        """Main function to run the combined system"""
        print(f"\n{'=' * 80}\nStarting Combined Property System\n{'=' * 80}")

        try:
            while True:
                current_time = datetime.now()
                
                # Check if it's time to run property matching
                time_since_last_match = (current_time - self.last_property_match_time).total_seconds()
                if time_since_last_match >= PROPERTY_MATCH_INTERVAL:
                    print(f"\n{'='*60}\nRunning property matching at {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                    self.match_properties_for_clients()
                    self.last_property_match_time = current_time
                
                # Always check for email replies on each cycle
                print(f"\n{'='*60}\nChecking for email replies at {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
                self.check_email_replies()
                
                # Sleep before next check
                print(f"\nWaiting {REPLY_CHECK_INTERVAL} seconds before next check...")
                time.sleep(REPLY_CHECK_INTERVAL)
                
        except KeyboardInterrupt:
            print("\nSystem interrupted by user. Shutting down...")
        except Exception as e:
            print(f"Error in main loop: {e}")
        finally:
            if self.conn:
                self.conn.close()
                print("Database connection closed.")
            print("System shutdown complete.")

    # ===== PROPERTY MATCHING FUNCTIONS =====
    
    def match_properties_for_clients(self):
        """Match properties for all active clients and send notifications"""
        self.refresh_db_connection()
        cursor = self.conn.cursor()

        try:
            # Check if tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clients_data'")
            if not cursor.fetchone():
                print("Error: clients_data table not found in database")
                return

            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='property_leads'")
            if not cursor.fetchone():
                print("Error: property_leads table not found in database")
                return

            # Get all active clients
            cursor.execute("SELECT * FROM clients_data WHERE status = 'active'")
            clients = cursor.fetchall()

            print(f"Found {len(clients)} active clients for property matching")

            # Process each client
            for client in clients:
                print(f"\nProcessing client: {client['name']} (ID: {client['id']})")

                # Find matching properties
                matches = self.find_matches_for_client(client)

                if matches:
                    print(f"Found {len(matches)} matching properties for {client['name']}")

                    # Try to send email notification
                    email_sent = self.send_match_email(client, matches)

                    # If email fails, save matches to file
                    if not email_sent:
                        print(f"Saving matches to file for {client['name']}...")
                        self.save_matches_to_file(client, matches)

                    # Log matches to database
                    for match in matches:
                        self.log_match_to_db(client['id'], match['id'], match['match_score'], email_sent)
                else:
                    print(f"No matching properties found for {client['name']}")

        except Exception as e:
            print(f"Error in property matching: {e}")

    def find_matches_for_client(self, client):
        """Find property matches for a client"""
        cursor = self.conn.cursor()

        # Get all properties
        cursor.execute("SELECT * FROM property_leads WHERE 1=1")
        properties = cursor.fetchall()

        matches = []

        for prop in properties:
            # Extract and standardize property size
            prop_size_value, prop_size_unit = self.parse_size(prop['size'])
            prop_size_std = self.standardize_size(prop_size_value, prop_size_unit)

            # Extract property price
            prop_price = self.parse_price(prop['price'])

            # Skip invalid properties
            if prop_size_std <= 0 or prop_price <= 0:
                continue

            # Check size match (convert client size to standard unit)
            client_min_size_std = self.standardize_size(client['min_size'], client['size_unit'])
            client_max_size_std = self.standardize_size(client['max_size'], client['size_unit'])

            size_match = (client_min_size_std * 0.8 <= prop_size_std <= client_max_size_std * 1.2)

            # Check budget match
            budget_match = (client['min_budget'] * 0.8 <= prop_price <= client['max_budget'] * 1.2)

            # Check location match
            location_match = True
            if client['preferred_location'] and prop['location']:
                client_location = client['preferred_location'].lower()
                prop_location = prop['location'].lower()
                location_match = any(loc in prop_location for loc in client_location.split(','))

            # Calculate match score
            match_score = 0
            if size_match and budget_match:
                # Size score
                if prop_size_std < client_min_size_std:
                    size_score = 70
                elif prop_size_std > client_max_size_std:
                    size_score = 80
                else:
                    size_score = 100

                # Budget score
                if prop_price < client['min_budget']:
                    budget_score = 90  # Under budget is good
                elif prop_price > client['max_budget']:
                    budget_score = 70  # Over budget is less desirable
                else:
                    budget_score = 100

                # Location score
                location_score = 100 if location_match else 60

                # Overall score
                match_score = (size_score * 0.4) + (budget_score * 0.4) + (location_score * 0.2)

                # If good match, add to results
                if match_score >= 70:
                    match = dict(prop)
                    match['match_score'] = match_score
                    match['size_value'] = prop_size_std
                    match['price_value'] = prop_price
                    matches.append(match)

        # Sort matches by score (highest first)
        matches.sort(key=lambda x: x['match_score'], reverse=True)
        return matches

    def parse_size(self, size_text):
        """Extract numeric size value and unit from text"""
        if not size_text or not isinstance(size_text, str):
            return 0, "marla"

        size_text = size_text.lower()

        # Try to extract pattern like "5 marla" or "10 kanal"
        pattern = r'(\d+(?:\.\d+)?)\s*(marla|kanal|sq\.?\s*(?:yards|yard|feet|ft|meter|m))'
        match = re.search(pattern, size_text)

        if match:
            size_value = float(match.group(1))
            unit_text = match.group(2).strip()

            if 'marla' in unit_text:
                size_unit = 'marla'
            elif 'kanal' in unit_text:
                size_unit = 'kanal'
            elif 'yard' in unit_text:
                size_unit = 'sq yards'
            else:
                size_unit = 'sq ft'
        else:
            # Try to extract just the number
            number_match = re.search(r'(\d+(?:\.\d+)?)', size_text)
            if number_match:
                size_value = float(number_match.group(1))
                size_unit = 'marla'  # Default
            else:
                size_value = 0
                size_unit = 'marla'

        return size_value, size_unit

    def standardize_size(self, size_value, size_unit):
        """Convert different size units to a standard unit (marla)"""
        if not size_value:
            return 0

        # Conversion factors to marla
        conversions = {
            "marla": 1,
            "kanal": 20,  # 1 kanal = 20 marla
            "sq yards": 0.15,  # Approx. 1 sq yard = 0.15 marla
            "sq feet": 0.0167,  # Approx. 1 sq ft = 0.0167 marla
            "sq ft": 0.0167
        }

        # Get the conversion factor (default to 1 if unit not recognized)
        factor = conversions.get(size_unit.lower(), 1)

        # Convert to standard unit (marla)
        standard_size = float(size_value) * factor

        return standard_size

    def parse_price(self, price_text):
        """Extract numeric price from text like 'Rs 25 Lacs' or '1.2 Crore'"""
        if not price_text or not isinstance(price_text, str):
            return 0

        price_text = price_text.lower()

        # Extract numeric part
        numeric_match = re.search(r'(\d+(?:\.\d+)?)', price_text)
        if not numeric_match:
            return 0

        value = float(numeric_match.group(1))

        # Apply multipliers based on Pakistani real estate terms
        if 'crore' in price_text:
            value = value * 10000000  # 1 crore = 10,000,000
        elif 'lac' in price_text or 'lakh' in price_text:
            value = value * 100000  # 1 lac/lakh = 100,000
        elif 'k' in price_text and not ('lak' in price_text or 'lac' in price_text):
            value = value * 1000  # 1k = 1,000

        return value

    def format_currency(self, amount):
        """Format amount as currency (e.g., 2,500,000 as 25 Lacs)"""
        if amount >= 10000000:  # 1 crore
            return f"{amount / 10000000:.2f} Crores"
        elif amount >= 100000:  # 1 lac
            return f"{amount / 100000:.0f} Lacs"
        else:
            return f"{amount:,}"

    def send_match_email(self, client, matches):
        """Send email to client with matching properties"""
        if not client['email'] or len(matches) == 0:
            return False

        # Create message
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Exclusive Property Matches for {client['name']} - {len(matches)} Properties Found"
        msg['From'] = EMAIL
        msg['To'] = client['email']

        # Create HTML content with enhanced professional layout
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Property Matches</title>
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
                .property {{
                    margin-bottom: 25px;
                    padding: 15px;
                    border: 1px solid #e0e0e0;
                    border-radius: 5px;
                    background-color: #ffffff;
                }}
                .property-title {{
                    font-size: 18px;
                    font-weight: bold;
                    color: #0a6eb4;
                    margin-bottom: 5px;
                }}
                .property-price {{
                    font-size: 16px;
                    font-weight: bold;
                    color: #28a745;
                    margin-bottom: 10px;
                }}
                .property-location {{
                    color: #666;
                    font-size: 14px;
                    margin-bottom: 10px;
                }}
                .property-details {{
                    margin-top: 10px;
                }}
                .property-details p {{
                    margin: 5px 0;
                }}
                .match-score {{
                    color: #28a745;
                    font-weight: bold;
                }}
                .contact-info {{
                    background-color: #f8f9fa;
                    padding: 10px;
                    border-radius: 5px;
                    margin-top: 10px;
                    border-left: 3px solid #0a6eb4;
                }}
                .video-link {{
                    color: #0a6eb4;
                    text-decoration: none;
                    font-weight: bold;
                }}
                .video-link:hover {{
                    text-decoration: underline;
                }}
                .highlight {{
                    background-color: #fffde7;
                    padding: 2px 4px;
                    border-radius: 3px;
                }}
                .btn {{
                    display: inline-block;
                    padding: 8px 15px;
                    background-color: #0a6eb4;
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                    font-weight: bold;
                }}
                .btn:hover {{
                    background-color: #085a95;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Exclusive Property Matches</h1>
                    <p>Specially Selected for {client['name']}</p>
                </div>

                <p>Dear {client['name']},</p>

                <p>We are pleased to present <strong>{len(matches)}</strong> exclusive properties that match your requirements. 
                Our intelligent matching system has analyzed your preferences and selected the following properties 
                that align with your budget, location preferences, and size requirements.</p>

                <div class="properties">
        """

        for i, match in enumerate(matches[:5]):  # Limit to top 5 matches
            # Safe access to potentially missing fields
            video_link = match.get('video_links', '') if 'video_links' in match else ''
            contact_number = match.get('contact_number', 'Not Available') if 'contact_number' in match else 'Not Available'
            contact_email = match.get('contact_email', 'Not Available') if 'contact_email' in match else 'Not Available'

            html += f"""
                <div class="property">
                    <div class="property-title">{match['title']}</div>
                    <div class="property-price">{match['price']}</div>
                    <div class="property-location">📍 {match['location']}</div>

                    <div class="property-details">
                        <p><strong>Size:</strong> {match['size']}</p>
                        <p><strong>Description:</strong> {match['description']}</p>
                        <p><strong>Match Score:</strong> <span class="match-score">{match['match_score']:.0f}%</span></p>

                        {f'<p><strong>Video Tour:</strong> <a href="{video_link}" class="video-link" target="_blank">View Property Tour</a></p>' if video_link else ''}

                        <div class="contact-info">
                            <p><strong>Contact Details:</strong></p>
                            <p>📞 Phone: {contact_number}</p>
                            <p>✉️ Email: {contact_email}</p>
                        </div>

                        <p style="margin-top: 15px;">
                            <a href="mailto:{contact_email}?subject=Inquiry about {match['title']}" class="btn">Contact Now</a>
                        </p>
                    </div>
                </div>
            """

        html += """
                </div>

                <p>These properties have been carefully selected based on your preferences. Our team is ready to assist 
                you with any additional information you might need or to arrange property visits.</p>

                <p>If you would like to modify your search criteria or have any questions, please don't hesitate to contact us 
                by replying to this email.</p>

                <p>Thank you for choosing our real estate services.</p>

                <p>Warm regards,<br>
                <strong>Your Real Estate Team</strong><br>
                Premier Property Consultants</p>

                <div class="footer">
                    <p>This email was sent to you based on your property search preferences.</p>
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

            print(f"✅ Email successfully sent to {client['name']} ({client['email']})")
            return True
        except Exception as e:
            print(f"❌ Failed to send email to {client['email']} - {e}")
            return False

    def log_match_to_db(self, client_id, property_id, match_score, email_sent):
        """Log the match and email notification to database"""
        cursor = self.conn.cursor()

        # Create a matches log table if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                property_id INTEGER,
                match_score REAL,
                email_sent BOOLEAN,
                notification_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients_data (id),
                FOREIGN KEY (property_id) REFERENCES property_leads (id)
            )
        ''')

        # Check if this match has already been notified
        cursor.execute('''
            SELECT id FROM match_notifications 
            WHERE client_id = ? AND property_id = ?
        ''', (client_id, property_id))

        if not cursor.fetchone():
            # Insert the new match notification
            cursor.execute('''
                INSERT INTO match_notifications 
                (client_id, property_id, match_score, email_sent)
                VALUES (?, ?, ?, ?)
            ''', (client_id, property_id, match_score, email_sent))

            self.conn.commit()
            return True
        return False

    def save_matches_to_file(self, client, matches, file_path=None):
        """Save matches to a file when email fails"""
        if not file_path:
            file_path = f"matches_{client['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

        # Create HTML content (simplified version of email template)
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Property Matches for {client['name']}</title>
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
                }}
                .header {{
                    background-color: #0a6eb4;
                    color: white;
                    padding: 20px;
                    text-align: center;
                    border-radius: 8px 8px 0 0;
                    margin-bottom: 20px;
                }}
                .property {{
                    margin-bottom: 25px;
                    padding: 15px;
                    border: 1px solid #e0e0e0;
                    border-radius: 5px;
                }}
                .property-title {{
                    font-size: 18px;
                    font-weight: bold;
                    color: #0a6eb4;
                }}
                .property-price {{
                    font-size: 16px;
                    font-weight: bold;
                    color: #28a745;
                }}
                .match-score {{
                    color: #28a745;
                    font-weight: bold;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Property Matches</h1>
                    <p>For {client['name']}</p>
                </div>

                <p>Found {len(matches)} properties matching the client's requirements.</p>

                <div class="properties">
        """

        for match in matches:
            html += f"""
                <div class="property">
                    <div class="property-title">{match['title']}</div>
                    <div class="property-price">{match['price']}</div>
                    <p><strong>Location:</strong> {match['location']}</p>
                    <p><strong>Size:</strong> {match['size']}</p>
                    <p><strong>Description:</strong> {match['description']}</p>
                    <p><strong>Match Score:</strong> <span class="match-score">{match['match_score']:.0f}%</span></p>
                </div>
            """

        html += """
                </div>
            </div>
        </body>
        </html>
        """

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f"Matches saved to file: {file_path}")
            return True
        except Exception as e:
            print(f"Error saving matches to file: {e}")
            return False

    # ===== EMAIL REPLY HANDLING FUNCTIONS =====
    
    def check_email_replies(self):
        """Check email inbox for replies from clients in the last 10 minutes"""
        print(f"\nChecking for email replies from the last 10 minutes...")

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

        # Add top matches
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


# Main execution function
def main():
    print("=" * 80)
    print("Starting Combined Real Estate Property System")
    print("=" * 80)
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create and run the combined system
    system = CombinedPropertySystem()
    system.run()


if __name__ == "__main__":
    main()