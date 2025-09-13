import sqlite3
import re
import smtplib
import imaplib
import email
import email.header
import random
import asyncio
import uvicorn
import os
import json
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends, Query, Body, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

# Configuration
EMAIL = "zuberipersonal@gmail.com"
PASSWORD = "lavfqbdauszbjuxp"
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465
DB_PATH = r"E:\BSAI-5th\DataMining\Real_State_Automation\real_estate.db"
API_KEY = "real_estate_api_key_123456"  # Change this in production

# API security
api_key_header = APIKeyHeader(name="X-API-Key")

# Office locations
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

# Meeting times
MEETING_HOURS = [f"{h}:00" for h in range(9, 18)]
MEETING_DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

# Background tasks control
should_run = True

# Pydantic models for API
class ClientBase(BaseModel):
    name: str
    email: EmailStr
    phone: str
    min_budget: float
    max_budget: float
    min_size: float
    max_size: float
    size_unit: str
    preferred_location: str
    status: str = "active"
    
class ClientCreate(ClientBase):
    pass

class ClientResponse(ClientBase):
    id: int
    created_at: str

class PropertyBase(BaseModel):
    title: str
    description: str
    price: str
    size: str
    location: str
    contact_number: Optional[str] = None
    contact_email: Optional[EmailStr] = None
    video_links: Optional[str] = None
    
class PropertyCreate(PropertyBase):
    pass

class PropertyResponse(PropertyBase):
    id: int
    created_at: str

class MatchResponse(BaseModel):
    client_id: int
    property_id: int
    match_score: float
    email_sent: bool
    notification_date: str

class MeetingResponse(BaseModel):
    id: int
    client_id: int
    meeting_date: str
    meeting_time: str
    office_name: str
    office_address: str
    status: str
    created_at: str

# Context manager for lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background tasks
    background_tasks = asyncio.create_task(run_background_tasks())
    yield
    # Stop background tasks
    global should_run
    should_run = False
    background_tasks.cancel()
    try:
        await background_tasks
    except asyncio.CancelledError:
        pass

# Initialize FastAPI
app = FastAPI(
    title="Real Estate Matching API",
    description="API for matching properties with clients and handling communications",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Modify this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency for API key validation
async def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    return api_key

# Database helpers
def get_db_connection():
    """Create a database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def dict_factory(cursor, row):
    """Convert database row to dictionary"""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

def get_db():
    """Get database connection with dict factory"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    return conn

# Property matching functions
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

def send_match_email(client, matches):
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
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL, PASSWORD)
            server.sendmail(EMAIL, client['email'], msg.as_string())

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

# Email reply handling functions
def decode_header(header):
    """Decode email header"""
    if not header:
        return ""

    decoded_header, encoding = email.header.decode_header(header)[0]

    if isinstance(decoded_header, bytes):
        return decoded_header.decode(encoding if encoding else 'utf-8', errors='replace')
    return decoded_header

def parse_from_address(from_header):
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

def get_email_body(msg):
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

def is_interested(body, subject):
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

def schedule_meeting():
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

def log_meeting(conn, client_id, meeting_info):
    """Log the scheduled meeting in the database"""
    cursor = conn.cursor()

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

    conn.commit()
    return cursor.lastrowid

def update_client_status(conn, client_id, status):
    """Update client status in the database"""
    cursor = conn.cursor()

    cursor.execute("UPDATE clients_data SET status = ? WHERE id = ?", (status, client_id))
    conn.commit()

def send_meeting_confirmation(client, matches, meeting_info):
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

    # Add top matches
    for match in top_matches:
        # Safe access for these fields
        contact_number = match.get('contact_number', 'Available at meeting')
        contact_email = match.get('contact_email', 'Available at meeting')

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

# Background tasks
async def process_property_matches():
    """Check for property matches and send notifications"""
    print(f"\n{'=' * 60}\nRunning property match check at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get all active clients
        cursor.execute("SELECT * FROM clients_data WHERE status = 'active'")
        clients = cursor.fetchall()
        
        print(f"Found {len(clients)} active clients to process")
        
        for client in clients:
            # Find matching properties
            matches = find_matches_for_client(client, conn)
            
            if matches:
                print(f"Found {len(matches)} matching properties for {client['name']}")
                
                # Send email notification
                email_sent = send_match_email(client, matches)
                
                # Log matches to database
                for match in matches:
                    log_match_to_db(conn, client['id'], match['id'], match['match_score'], email_sent)
            else:
                print(f"No matching properties found for {client['name']}")
        
        conn.close()
    except Exception as e:
        print(f"Error in process_property_matches: {e}")

async def check_email_replies():
    """Check for client email replies"""
    print(f"\n{'=' * 60}\nChecking email replies at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Connect to IMAP server
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(EMAIL, PASSWORD)
        mail.select('inbox')
        
        # Calculate time 10 minutes ago
        ten_minutes_ago = (datetime.now() - timedelta(minutes=10))
        date_string = ten_minutes_ago.strftime("%d-%b-%Y")
        
        # Search for emails
        status, data = mail.search(None, f'SINCE "{date_string}"')
        
        if status != 'OK':
            print("Error searching for emails")
            return
        
        email_ids = data[0].split()
        
        if not email_ids:
            print("No new emails found")
            return
        
        print(f"Found {len(email_ids)} emails to process")
        
        conn = get_db_connection()
        
        # Process each email
        for email_id in email_ids:
            status, data = mail.fetch(email_id, '(RFC822)')
            
            if status != 'OK':
                continue
                
            msg = email.message_from_bytes(data[0][1])
            
            # Get email details
            date_tuple = email.utils.parsedate_tz(msg['Date'])
            if date_tuple:
                email_time = datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))
                if email_time < ten_minutes_ago:
                    # Skip emails older than 10 minutes
                    continue
            
            subject = decode_header(msg['subject'])
            from_address = parse_from_address(msg['from'])
            body = get_email_body(msg)
            
            print(f"Processing email from: {from_address}")
            
            # Check if client exists
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM clients_data WHERE email = ?", (from_address,))
            client = cursor.fetchone()
            
            if client:
                print(f"Matched to client: {client['name']}")
                
                # Check if interested
                if is_interested(body, subject):
                    print(f"Client shows interest! Scheduling meeting...")
                    
                    # Get client's property matches
                    cursor.execute("""
                        SELECT p.* FROM match_notifications m
                        JOIN property_leads p ON m.property_id = p.id
                        WHERE m.client_id = ? ORDER BY m.match_score DESC
                    """, (client['id'],))
                    
                    matches = cursor.fetchall()
                    
                    if matches:
                        # Schedule meeting
                        meeting_info = schedule_meeting()
                        
                        # Log meeting in database
                        log_meeting(conn, client['id'], meeting_info)
                        
                        # Send meeting confirmation
                        send_meeting_confirmation(client, matches, meeting_info)
                        
                        # Update client status
                        update_client_status(conn, client['id'], "meeting_scheduled")
        
        conn.close()
        mail.logout()
        
    except Exception as e:
        print(f"Error in check_email_replies: {e}")

async def run_background_tasks():
    """Run all background tasks periodically"""
    global should_run
    
    # Initial delay to allow server startup
    await asyncio.sleep(5)
    
    while should_run:
        try:
            # Run property matching
            await process_property_matches()
            
            # Run email reply checking
            await check_email_replies()
            
            # Wait before next run (5 minutes)
            for _ in range(60 * 5):  # 5 minutes in seconds
                if not should_run:
                    break
                await asyncio.sleep(1)
                
        except Exception as e:
            print(f"Error in background tasks: {e}")
            await asyncio.sleep(60)  # Wait a minute before retrying

# API Routes
@app.get("/", tags=["Health"])
async def root():
    """API health check endpoint"""
    return {
        "message": "Real Estate Matching API is running",
        "version": "1.0.0",
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/clients", response_model=List[ClientResponse], tags=["Clients"])
async def get_clients(
    skip: int = 0, 
    limit: int = 100, 
    status: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
):
    """Get all clients with optional filtering"""
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM clients_data WHERE 1=1"
    params = []
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, skip])
    
    cursor.execute(query, params)
    clients = cursor.fetchall()
    conn.close()
    
    return clients

@app.get("/api/clients/{client_id}", response_model=ClientResponse, tags=["Clients"])
async def get_client(
    client_id: int,
    api_key: str = Depends(verify_api_key)
):
    """Get a single client by ID"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM clients_data WHERE id = ?", (client_id,))
    client = cursor.fetchone()
    conn.close()
    
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    
    return client

@app.post("/api/clients", response_model=ClientResponse, status_code=201, tags=["Clients"])
async def create_client(
    client: ClientCreate,
    api_key: str = Depends(verify_api_key)
):
    """Create a new client"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO clients_data (
            name, email, phone, min_budget, max_budget, 
            min_size, max_size, size_unit, preferred_location, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        client.name, client.email, client.phone,
        client.min_budget, client.max_budget,
        client.min_size, client.max_size,
        client.size_unit, client.preferred_location, client.status
    ))
    
    conn.commit()
    client_id = cursor.lastrowid
    
    # Get the created client
    cursor.execute("SELECT * FROM clients_data WHERE id = ?", (client_id,))
    new_client = cursor.fetchone()
    conn.close()
    
    return new_client

@app.put("/api/clients/{client_id}", response_model=ClientResponse, tags=["Clients"])
async def update_client(
    client_id: int,
    client: ClientCreate,
    api_key: str = Depends(verify_api_key)
):
    """Update an existing client"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if client exists
    cursor.execute("SELECT id FROM clients_data WHERE id = ?", (client_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Update client
    cursor.execute("""
        UPDATE clients_data SET
            name = ?, email = ?, phone = ?, min_budget = ?, max_budget = ?,
            min_size = ?, max_size = ?, size_unit = ?, preferred_location = ?, status = ?
        WHERE id = ?
    """, (
        client.name, client.email, client.phone,
        client.min_budget, client.max_budget,
        client.min_size, client.max_size,
        client.size_unit, client.preferred_location, client.status,
        client_id
    ))
    
    conn.commit()
    
    # Get updated client
    cursor.execute("SELECT * FROM clients_data WHERE id = ?", (client_id,))
    updated_client = cursor.fetchone()
    conn.close()
    
    return updated_client

@app.delete("/api/clients/{client_id}", status_code=204, tags=["Clients"])
async def delete_client(
    client_id: int,
    api_key: str = Depends(verify_api_key)
):
    """Delete a client"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if client exists
    cursor.execute("SELECT id FROM clients_data WHERE id = ?", (client_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Delete client
    cursor.execute("DELETE FROM clients_data WHERE id = ?", (client_id,))
    conn.commit()
    conn.close()
    
    return None

@app.get("/api/properties", response_model=List[PropertyResponse], tags=["Properties"])
async def get_properties(
    skip: int = 0, 
    limit: int = 100,
    location: Optional[str] = None,
    api_key: str = Depends(verify_api_key)
):
    """Get all properties with optional filtering"""
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM property_leads WHERE 1=1"
    params = []
    
    if location:
        query += " AND location LIKE ?"
        params.append(f"%{location}%")
    
    query += " LIMIT ? OFFSET ?"
    params.extend([limit, skip])
    
    cursor.execute(query, params)
    properties = cursor.fetchall()
    conn.close()
    
    return properties

@app.get("/api/properties/{property_id}", response_model=PropertyResponse, tags=["Properties"])
async def get_property(
    property_id: int,
    api_key: str = Depends(verify_api_key)
):
    """Get a single property by ID"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM property_leads WHERE id = ?", (property_id,))
    property = cursor.fetchone()
    conn.close()
    
    if not property:
        raise HTTPException(status_code=404, detail="Property not found")
    
    return property

@app.post("/api/properties", response_model=PropertyResponse, status_code=201, tags=["Properties"])
async def create_property(
    property: PropertyCreate,
    api_key: str = Depends(verify_api_key)
):
    """Create a new property"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO property_leads (
            title, description, price, size, location, 
            contact_number, contact_email, video_links
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        property.title, property.description, property.price,
        property.size, property.location, property.contact_number,
        property.contact_email, property.video_links
    ))
    
    conn.commit()
    property_id = cursor.lastrowid
    
    # Get the created property
    cursor.execute("SELECT * FROM property_leads WHERE id = ?", (property_id,))
    new_property = cursor.fetchone()
    conn.close()
    
    return new_property

@app.put("/api/properties/{property_id}", response_model=PropertyResponse, tags=["Properties"])
async def update_property(
    property_id: int,
    property: PropertyCreate,
    api_key: str = Depends(verify_api_key)
):
    """Update an existing property"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if property exists
    cursor.execute("SELECT id FROM property_leads WHERE id = ?", (property_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Update property
    cursor.execute("""
        UPDATE property_leads SET
            title = ?, description = ?, price = ?, size = ?,
            location = ?, contact_number = ?, contact_email = ?, video_links = ?
        WHERE id = ?
    """, (
        property.title, property.description, property.price,
        property.size, property.location, property.contact_number,
        property.contact_email, property.video_links, property_id
    ))
    
    conn.commit()
    
    # Get updated property
    cursor.execute("SELECT * FROM property_leads WHERE id = ?", (property_id,))
    updated_property = cursor.fetchone()
    conn.close()
    
    return updated_property

@app.delete("/api/properties/{property_id}", status_code=204, tags=["Properties"])
async def delete_property(
    property_id: int,
    api_key: str = Depends(verify_api_key)
):
    """Delete a property"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if property exists
    cursor.execute("SELECT id FROM property_leads WHERE id = ?", (property_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Delete property
    cursor.execute("DELETE FROM property_leads WHERE id = ?", (property_id,))
    conn.commit()
    conn.close()
    
    return None

@app.get("/api/matches", response_model=List[MatchResponse], tags=["Matches"])
async def get_matches(
    client_id: Optional[int] = None,
    property_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    api_key: str = Depends(verify_api_key)
):
    """Get property matches with optional filtering"""
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM match_notifications WHERE 1=1"
    params = []
    
    if client_id:
        query += " AND client_id = ?"
        params.append(client_id)
    
    if property_id:
        query += " AND property_id = ?"
        params.append(property_id)
    
    query += " ORDER BY notification_date DESC LIMIT ? OFFSET ?"
    params.extend([limit, skip])
    
    cursor.execute(query, params)
    matches = cursor.fetchall()
    conn.close()
    
    return matches

@app.get("/api/matches/client/{client_id}", tags=["Matches"])
async def get_client_matches(
    client_id: int,
    skip: int = 0,
    limit: int = 100,
    api_key: str = Depends(verify_api_key)
):
    """Get detailed property matches for a specific client"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Check if client exists
    cursor.execute("SELECT id FROM clients_data WHERE id = ?", (client_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Client not found")
    
    # Get detailed matches
    cursor.execute("""
        SELECT m.*, p.title, p.description, p.price, p.size, p.location 
        FROM match_notifications m
        JOIN property_leads p ON m.property_id = p.id
        WHERE m.client_id = ?
        ORDER BY m.match_score DESC
        LIMIT ? OFFSET ?
    """, (client_id, limit, skip))
    
    matches = cursor.fetchall()
    conn.close()
    
    return {"client_id": client_id, "matches": matches}

@app.get("/api/meetings", tags=["Meetings"])
async def get_meetings(
    client_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    api_key: str = Depends(verify_api_key)
):
    """Get scheduled meetings with optional filtering"""
    conn = get_db()
    cursor = conn.cursor()
    
    query = "SELECT * FROM scheduled_meetings WHERE 1=1"
    params = []
    
    if client_id:
        query += " AND client_id = ?"
        params.append(client_id)
    
    if status:
        query += " AND status = ?"
        params.append(status)
    
    query += " ORDER BY meeting_date DESC LIMIT ? OFFSET ?"
    params.extend([limit, skip])
    
    cursor.execute(query, params)
    meetings = cursor.fetchall()
    conn.close()
    
    return {"meetings": meetings}

@app.post("/api/run/property-matching", tags=["Tasks"])
async def run_property_matching_now(
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """Run property matching task immediately"""
    try:
        background_tasks.add_task(process_property_matches)
        return {"message": "Property matching task started", "status": "success"}
    except Exception as e:
        return {"message": f"Error starting task: {str(e)}", "status": "error"}

@app.post("/api/run/email-check", tags=["Tasks"])
async def run_email_check_now(
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """Run email reply check task immediately"""
    try:
        background_tasks.add_task(check_email_replies)
        return {"message": "Email check task started", "status": "success"}
    except Exception as e:
        return {"message": f"Error starting task: {str(e)}", "status": "error"}

@app.get("/api/stats", tags=["Statistics"])
async def get_stats(
    api_key: str = Depends(verify_api_key)
):
    """Get system statistics"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Get counts
    cursor.execute("SELECT COUNT(*) as client_count FROM clients_data")
    client_count = cursor.fetchone()['client_count']
    
    cursor.execute("SELECT COUNT(*) as property_count FROM property_leads")
    property_count = cursor.fetchone()['property_count']
    
    cursor.execute("SELECT COUNT(*) as match_count FROM match_notifications")
    match_count = cursor.fetchone()['match_count']
    
    cursor.execute("SELECT COUNT(*) as meeting_count FROM scheduled_meetings")
    meeting_count = cursor.fetchone().get('meeting_count', 0)
    
    # Get recent activity
    cursor.execute("""
        SELECT 'match' as type, notification_date as date FROM match_notifications
        UNION ALL
        SELECT 'meeting' as type, created_at as date FROM scheduled_meetings
        ORDER BY date DESC LIMIT 10
    """)
    recent_activity = cursor.fetchall()
    
    conn.close()
    
    return {
        "counts": {
            "clients": client_count,
            "properties": property_count,
            "matches": match_count,
            "meetings": meeting_count
        },
        "recent_activity": recent_activity,
        "system_status": "healthy",
        "last_updated": datetime.now().isoformat()
    }

# Start server directly when script is run
if __name__ == "__main__":
    uvicorn.run("real_estate_api:app", host="0.0.0.0", port=8000, reload=True)