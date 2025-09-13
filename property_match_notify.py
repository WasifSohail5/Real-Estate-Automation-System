import sqlite3
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime

# Email configuration
SENDER_EMAIL = "zuberipersonal@gmail.com"
EMAIL_PASSWORD = "lavfqbdauszbjuxp"


def connect_to_db(db_path=r"E:\BSAI-5th\DataMining\Real_State_Automation\real_estate.db"):
    """Connect to the database"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row  # This enables column access by name
    return conn


def parse_size(size_text):
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


def standardize_size(size_value, size_unit):
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


def parse_price(price_text):
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


def find_matches_for_client(client, conn):
    """Find property matches for a client"""
    cursor = conn.cursor()

    # Get all properties
    cursor.execute("SELECT * FROM property_leads WHERE 1=1")
    properties = cursor.fetchall()

    matches = []

    for prop in properties:
        # Extract and standardize property size
        prop_size_value, prop_size_unit = parse_size(prop['size'])
        prop_size_std = standardize_size(prop_size_value, prop_size_unit)

        # Extract property price
        prop_price = parse_price(prop['price'])

        # Skip invalid properties
        if prop_size_std <= 0 or prop_price <= 0:
            continue

        # Check size match (convert client size to standard unit)
        client_min_size_std = standardize_size(client['min_size'], client['size_unit'])
        client_max_size_std = standardize_size(client['max_size'], client['size_unit'])

        size_match = (client_min_size_std * 0.8 <= prop_size_std <= client_max_size_std * 1.2)

        # Check budget match
        budget_match = (client['min_budget'] * 0.8 <= prop_price <= client['max_budget'] * 1.2)

        # Check location match
        location_match = True
        if client['preferred_location'] and prop['location']:
            client_location = client['preferred_location'].lower()
            prop_location = prop['location'].lower()

            # Check if client's preferred location is in property location
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


def format_currency(amount):
    """Format amount as currency (e.g., 2,500,000 as 25 Lacs)"""
    if amount >= 10000000:  # 1 crore
        return f"{amount / 10000000:.2f} Crores"
    elif amount >= 100000:  # 1 lac
        return f"{amount / 100000:.0f} Lacs"
    else:
        return f"{amount:,}"


def send_match_email(client, matches):
    """Send email to client with matching properties"""
    if not client['email'] or len(matches) == 0:
        return False

    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Exclusive Property Matches for {client['name']} - {len(matches)} Properties Found"
    msg['From'] = SENDER_EMAIL
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
        video_link = match.get('video_links', '')
        contact_number = match.get('contact_number', 'Not Available')
        contact_email = match.get('contact_email', 'Not Available')

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

            <p>If you would like to modify your search criteria or have any questions, please don't hesitate to contact us.</p>

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
        # Use SMTP_SSL directly (port 465) instead of STARTTLS
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER_EMAIL, EMAIL_PASSWORD)
            server.sendmail(SENDER_EMAIL, client['email'], msg.as_string())

        print(f"✅ Email successfully sent to {client['name']} ({client['email']})")
        return True
    except Exception as e:
        print(f"❌ Failed to send email to {client['email']} - {e}")
        return False


def log_match_to_db(conn, client_id, property_id, match_score, email_sent):
    """Log the match and email notification to database"""
    cursor = conn.cursor()

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

        conn.commit()
        return True
    return False


def save_matches_to_file(client, matches, file_path=None):
    """Save matches to a file when email fails"""
    if not file_path:
        file_path = f"matches_{client['name']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

    # Create HTML content
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
            .property-location {{
                color: #666;
                font-size: 14px;
            }}
            .property-details {{
                margin-top: 10px;
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
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Property Matches</h1>
                <p>For {client['name']}</p>
            </div>

            <p>Found {len(matches)} properties matching your requirements!</p>

            <div class="properties">
    """

    for i, match in enumerate(matches):
        # Safe access to potentially missing fields
        video_link = match.get('video_links', '')
        contact_number = match.get('contact_number', 'Not Available')
        contact_email = match.get('contact_email', 'Not Available')

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
                </div>
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


def main():
    """Main function to run the property matching and notification system"""
    print("Starting Property Matching and Email Notification System")
    print(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Connect to database
    conn = connect_to_db()
    cursor = conn.cursor()

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

        print(f"Found {len(clients)} active clients")

        # Process each client
        for client in clients:
            print(f"\nProcessing client: {client['name']} (ID: {client['id']})")

            # Find matching properties
            matches = find_matches_for_client(client, conn)

            if matches:
                print(f"Found {len(matches)} matching properties for {client['name']}")

                # Try to send email notification
                email_sent = send_match_email(client, matches)

                # If email fails, save matches to file
                if not email_sent:
                    print(f"Saving matches to file for {client['name']}...")
                    save_matches_to_file(client, matches)

                # Log matches to database
                for match in matches:
                    log_match_to_db(conn, client['id'], match['id'], match['match_score'], email_sent)
            else:
                print(f"No matching properties found for {client['name']}")

        print("\nProperty matching and notification process completed")

    except Exception as e:
        print(f"Error in property matching: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()