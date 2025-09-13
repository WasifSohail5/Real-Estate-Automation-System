import sqlite3
import logging
import time
import re
import random
from datetime import datetime
import os
import pandas as pd

# Try to import WhatsApp integration
try:
    import pywhatkit

    whatsapp_available = True
except ImportError:
    whatsapp_available = False
    print("pywhatkit not available. WhatsApp functionality will be limited.")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('client_matching.log'), logging.StreamHandler()]
)
logger = logging.getLogger('client_matching')


class ClientMatchingSystem:
    """System to match client requirements with existing property listings"""

    def __init__(self, db_path="database.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.connect_db()
        self.setup_database()

    def connect_db(self):
        """Connect to the SQLite database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # This enables column access by name
            self.cursor = self.conn.cursor()
            logger.info(f"Connected to database: {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise

    def setup_database(self):
        """Set up new tables for client management"""
        try:
            # Check if the property_leads table exists (should be there from scraping)
            self.cursor.execute('''
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='property_leads'
            ''')
            if not self.cursor.fetchone():
                logger.warning("property_leads table doesn't exist! Make sure you've run the scraper.")
                logger.info("Creating empty property_leads table as fallback...")
                self.cursor.execute('''
                    CREATE TABLE IF NOT EXISTS property_leads (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT,
                        description TEXT,
                        price TEXT,
                        location TEXT,
                        property_type TEXT,
                        size TEXT,
                        seller_name TEXT,
                        contact_number TEXT,
                        listing_url TEXT,
                        source TEXT,
                        urgency TEXT,
                        status TEXT DEFAULT 'available',
                        added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            else:
                logger.info("Found existing property_leads table. Good!")

            # Create table for clients/customers
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS clients (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    email TEXT,
                    preferred_location TEXT,
                    min_size REAL,
                    max_size REAL,
                    size_unit TEXT DEFAULT 'marla',
                    min_budget REAL,
                    max_budget REAL,
                    requirements TEXT,
                    status TEXT DEFAULT 'active',
                    added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create table for matches between clients and properties
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS client_matches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER,
                    property_id INTEGER,
                    match_score REAL,
                    notification_sent BOOLEAN DEFAULT 0,
                    notification_date TIMESTAMP,
                    client_response TEXT,  -- interested, not_interested, no_response
                    meeting_scheduled BOOLEAN DEFAULT 0,
                    meeting_date TIMESTAMP,
                    notes TEXT,
                    FOREIGN KEY (client_id) REFERENCES clients (id),
                    FOREIGN KEY (property_id) REFERENCES property_leads (id),
                    UNIQUE(client_id, property_id)
                )
            ''')

            # Create table for notification history
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id INTEGER,
                    property_id INTEGER,
                    message TEXT,
                    sent_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    method TEXT,  -- whatsapp, email, sms
                    status TEXT,  -- sent, failed, delivered
                    FOREIGN KEY (client_id) REFERENCES clients (id),
                    FOREIGN KEY (property_id) REFERENCES property_leads (id)
                )
            ''')

            self.conn.commit()
            logger.info("Database tables set up successfully")

            # Check if we have any sample data
            self.cursor.execute("SELECT COUNT(*) FROM clients")
            client_count = self.cursor.fetchone()[0]
            logger.info(f"Found {client_count} existing clients in database")

        except sqlite3.Error as e:
            logger.error(f"Error setting up database tables: {e}")
            raise

    def add_client(self, client_data):
        """Add a new client/customer to the database"""
        try:
            # Parse size values
            min_size = float(client_data.get('min_size', 0))
            max_size = float(client_data.get('max_size', 0)) if client_data.get('max_size') else min_size * 1.5

            # Parse budget values
            min_budget = float(client_data.get('min_budget', 0))
            max_budget = float(client_data.get('max_budget', 0)) if client_data.get('max_budget') else min_budget * 1.5

            self.cursor.execute('''
                INSERT INTO clients (
                    name, phone, email, preferred_location, 
                    min_size, max_size, size_unit, 
                    min_budget, max_budget, requirements, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                client_data['name'],
                client_data['phone'],
                client_data.get('email', ''),
                client_data.get('preferred_location', ''),
                min_size,
                max_size,
                client_data.get('size_unit', 'marla'),
                min_budget,
                max_budget,
                client_data.get('requirements', ''),
                client_data.get('status', 'active')
            ))

            self.conn.commit()
            client_id = self.cursor.lastrowid
            logger.info(f"Added new client with ID {client_id}: {client_data['name']}")

            # After adding a client, find potential property matches
            self.find_matches_for_client(client_id)

            return client_id
        except sqlite3.Error as e:
            logger.error(f"Error adding client: {e}")
            return None

    def get_all_clients(self):
        """Get all clients from the database"""
        try:
            self.cursor.execute("SELECT * FROM clients ORDER BY added_date DESC")
            clients = [dict(row) for row in self.cursor.fetchall()]
            return clients
        except sqlite3.Error as e:
            logger.error(f"Error getting clients: {e}")
            return []

    def get_client(self, client_id):
        """Get a specific client by ID"""
        try:
            self.cursor.execute("SELECT * FROM clients WHERE id = ?", (client_id,))
            client = self.cursor.fetchone()
            return dict(client) if client else None
        except sqlite3.Error as e:
            logger.error(f"Error getting client: {e}")
            return None

    def update_client(self, client_id, client_data):
        """Update client information"""
        try:
            # Get the current client data first
            current = self.get_client(client_id)
            if not current:
                return False

            # Update with new values where provided
            updates = {}
            for key in ['name', 'phone', 'email', 'preferred_location', 'min_size',
                        'max_size', 'size_unit', 'min_budget', 'max_budget', 'requirements', 'status']:
                updates[key] = client_data.get(key, current[key])

            self.cursor.execute('''
                UPDATE clients SET
                name = ?, phone = ?, email = ?, preferred_location = ?,
                min_size = ?, max_size = ?, size_unit = ?,
                min_budget = ?, max_budget = ?, requirements = ?, status = ?,
                last_updated = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                updates['name'], updates['phone'], updates['email'], updates['preferred_location'],
                updates['min_size'], updates['max_size'], updates['size_unit'],
                updates['min_budget'], updates['max_budget'], updates['requirements'], updates['status'],
                client_id
            ))

            self.conn.commit()
            logger.info(f"Updated client with ID {client_id}")

            # After updating a client, find potential property matches
            self.find_matches_for_client(client_id)

            return True
        except sqlite3.Error as e:
            logger.error(f"Error updating client: {e}")
            return False

    def delete_client(self, client_id):
        """Delete a client from the database"""
        try:
            # First delete any matches associated with this client
            self.cursor.execute("DELETE FROM client_matches WHERE client_id = ?", (client_id,))

            # Then delete notifications
            self.cursor.execute("DELETE FROM notifications WHERE client_id = ?", (client_id,))

            # Finally delete the client
            self.cursor.execute("DELETE FROM clients WHERE id = ?", (client_id,))

            self.conn.commit()
            logger.info(f"Deleted client with ID {client_id}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Error deleting client: {e}")
            return False

    def _parse_size_from_text(self, size_text):
        """Extract size value and unit from text"""
        if not size_text or not isinstance(size_text, str):
            return 0, "marla"

        size_text = size_text.lower()
        size_value = 0
        size_unit = "marla"  # Default

        # Try to extract pattern like "5 marla" or "10 kanal"
        pattern = r'(\d+(?:\.\d+)?)\s*(marla|kanal|sq\.?\s*(?:ft|feet|yd|yard|meter|m))'
        match = re.search(pattern, size_text)

        if match:
            try:
                size_value = float(match.group(1))
                unit_text = match.group(2).strip()

                if 'marla' in unit_text:
                    size_unit = 'marla'
                elif 'kanal' in unit_text:
                    size_unit = 'kanal'
                elif any(term in unit_text for term in ['sq', 'feet', 'ft']):
                    size_unit = 'sq ft'
            except (ValueError, IndexError):
                pass
        else:
            # Try to extract just the number
            number_match = re.search(r'(\d+(?:\.\d+)?)', size_text)
            if number_match:
                try:
                    size_value = float(number_match.group(1))
                except (ValueError, IndexError):
                    pass

        return size_value, size_unit

    def _standardize_size(self, size_value, size_unit):
        """Convert different size units to a standard unit (marla)"""
        if not size_value:
            return 0

        # Conversion factors to marla
        conversions = {
            "marla": 1,
            "kanal": 20,  # 1 kanal = 20 marla
            "sq ft": 0.00367,  # Approx. 1 sq ft = 0.00367 marla
            "square feet": 0.00367,
            "sqft": 0.00367
        }

        # Get the conversion factor (default to 1 if unit not recognized)
        factor = conversions.get(size_unit.lower(), 1)

        # Convert to standard unit (marla)
        standard_size = float(size_value) * factor

        return standard_size

    def _parse_price_to_numeric(self, price_text):
        """Convert price text (e.g., "PKR 1.5 crore") to numeric value"""
        if not price_text or not isinstance(price_text, str):
            return 0

        price_text = price_text.lower()

        # Extract numeric part
        numeric_match = re.search(r'(\d+(?:\.\d+)?)', price_text)
        if not numeric_match:
            return 0

        try:
            value = float(numeric_match.group(1))

            # Apply multipliers based on Pakistani real estate terms
            if 'crore' in price_text:
                value = value * 10000000  # 1 crore = 10,000,000
            elif 'lac' in price_text or 'lakh' in price_text:
                value = value * 100000  # 1 lac/lakh = 100,000
            elif 'k' in price_text and not ('lak' in price_text or 'lac' in price_text):
                value = value * 1000  # 1k = 1,000

            return value
        except (ValueError, IndexError):
            return 0

    def find_matches_for_client(self, client_id):
        """Find property matches for a specific client"""
        try:
            # Get client details
            client = self.get_client(client_id)
            if not client:
                logger.error(f"Client with ID {client_id} not found")
                return []

            # Get available properties
            self.cursor.execute('''
                SELECT * FROM property_leads 
                WHERE status != 'sold'
            ''')
            properties = self.cursor.fetchall()

            matches = []

            for prop in properties:
                # Process the property data
                property_dict = dict(prop)

                # Extract and standardize property size
                prop_size_value, prop_size_unit = self._parse_size_from_text(property_dict['size'])
                prop_size_std = self._standardize_size(prop_size_value, prop_size_unit)

                # Extract numeric price
                prop_price = self._parse_price_to_numeric(property_dict['price'])

                # Skip properties with invalid price or size
                if prop_price <= 0 or prop_size_std <= 0:
                    continue

                # Check size match
                client_min_size_std = self._standardize_size(client['min_size'], client['size_unit'])
                client_max_size_std = self._standardize_size(client['max_size'], client['size_unit'])

                size_match = (client_min_size_std * 0.8 <= prop_size_std <= client_max_size_std * 1.2)

                # Check budget match
                budget_match = (client['min_budget'] * 0.8 <= prop_price <= client['max_budget'] * 1.2)

                # Check location match if client has preferences
                location_match = True
                if client['preferred_location'] and isinstance(property_dict['location'], str):
                    location_match = client['preferred_location'].lower() in property_dict['location'].lower()

                # Calculate match score
                if size_match and budget_match and location_match:
                    # Size match score (0-100)
                    if prop_size_std < client_min_size_std:
                        size_score = 70
                    elif prop_size_std > client_max_size_std:
                        size_score = 80
                    else:
                        # Perfect fit
                        size_ratio = prop_size_std / ((client_min_size_std + client_max_size_std) / 2)
                        size_score = 100 - min(20, abs(1 - size_ratio) * 40)

                    # Budget match score (0-100)
                    if prop_price < client['min_budget']:
                        budget_score = 90  # Under budget is good
                    elif prop_price > client['max_budget']:
                        budget_score = 70  # Over budget is less desirable
                    else:
                        # Within budget
                        budget_ratio = prop_price / ((client['min_budget'] + client['max_budget']) / 2)
                        budget_score = 100 - min(20, abs(1 - budget_ratio) * 40)

                    # Location score (0-100)
                    location_score = 100 if location_match else 50

                    # Overall score (weighted average)
                    match_score = (size_score * 0.4) + (budget_score * 0.4) + (location_score * 0.2)

                    # If good enough match, save it
                    if match_score >= 60:
                        match_data = {
                            'client_id': client_id,
                            'property_id': property_dict['id'],
                            'match_score': match_score
                        }
                        matches.append(match_data)

                        # Add to database
                        self._save_match(match_data)

            logger.info(f"Found {len(matches)} potential matches for client {client_id}")
            return matches
        except Exception as e:
            logger.error(f"Error finding matches for client: {e}")
            return []

    def _save_match(self, match_data):
        """Save a client-property match to the database"""
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO client_matches (
                    client_id, property_id, match_score
                ) VALUES (?, ?, ?)
            ''', (
                match_data['client_id'],
                match_data['property_id'],
                match_data['match_score']
            ))
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error saving match: {e}")
            return False

    def get_client_matches(self, client_id):
        """Get all matches for a specific client"""
        try:
            self.cursor.execute('''
                SELECT cm.*, pl.title, pl.price, pl.location, pl.size, pl.description, pl.urgency
                FROM client_matches cm
                JOIN property_leads pl ON cm.property_id = pl.id
                WHERE cm.client_id = ?
                ORDER BY cm.match_score DESC
            ''', (client_id,))

            matches = [dict(row) for row in self.cursor.fetchall()]
            return matches
        except sqlite3.Error as e:
            logger.error(f"Error getting client matches: {e}")
            return []

    def get_all_matches(self):
        """Get all client-property matches"""
        try:
            self.cursor.execute('''
                SELECT cm.*, c.name AS client_name, c.phone AS client_phone,
                       pl.title AS property_title, pl.price AS property_price, 
                       pl.location AS property_location
                FROM client_matches cm
                JOIN clients c ON cm.client_id = c.id
                JOIN property_leads pl ON cm.property_id = pl.id
                ORDER BY cm.match_score DESC
            ''')

            matches = [dict(row) for row in self.cursor.fetchall()]
            return matches
        except sqlite3.Error as e:
            logger.error(f"Error getting all matches: {e}")
            return []

    def get_unnotified_matches(self, min_score=70):
        """Get matches that haven't been notified yet"""
        try:
            self.cursor.execute('''
                SELECT cm.*, c.name AS client_name, c.phone AS client_phone, c.email AS client_email,
                       pl.title AS property_title, pl.price AS property_price, 
                       pl.location AS property_location, pl.size AS property_size,
                       pl.description AS property_description
                FROM client_matches cm
                JOIN clients c ON cm.client_id = c.id
                JOIN property_leads pl ON cm.property_id = pl.id
                WHERE cm.notification_sent = 0
                AND cm.match_score >= ?
                ORDER BY cm.match_score DESC
            ''', (min_score,))

            matches = [dict(row) for row in self.cursor.fetchall()]
            return matches
        except sqlite3.Error as e:
            logger.error(f"Error getting unnotified matches: {e}")
            return []

    def format_whatsapp_message(self, match):
        """Format a WhatsApp message for a property match"""
        message = f"*PROPERTY MATCH ALERT!*\n\n"
        message += f"Hello {match['client_name']},\n\n"

        message += f"We've found a property that matches your requirements!\n\n"

        message += f"*{match['property_title']}*\n\n"

        # Add price
        message += f"*Price:* {match['property_price']}\n"

        # Add location
        message += f"*Location:* {match['property_location']}\n"

        # Add size
        message += f"*Size:* {match['property_size']}\n\n"

        # Add description (shortened)
        if match['property_description']:
            desc = match['property_description']
            if len(desc) > 150:
                desc = desc[:147] + "..."
            message += f"{desc}\n\n"

        # Add match score
        message += f"*Match Score:* {int(match['match_score'])}% match with your requirements!\n\n"

        # Add call to action
        message += "If you're interested in this property, please reply 'YES' to this message, and our agent will contact you with more details and arrange a viewing.\n\n"

        message += f"Thank you for choosing our agency!\n"
        message += f"[Ref: PM-{match['id']}]"

        return message

    def send_whatsapp_notification(self, match):
        """Send WhatsApp notification for a property match"""
        if not whatsapp_available:
            logger.warning("WhatsApp is not available. Install pywhatkit package.")
            return False

        try:
            # Format the message
            message = self.format_whatsapp_message(match)

            # Get client's phone number
            phone = match['client_phone'].strip()
            if not phone.startswith('+'):
                phone = '+' + phone  # Add country code if missing

            # Get current time for scheduling
            now = datetime.now()

            # Schedule message to be sent 1 minute from now
            hour = now.hour
            minute = now.minute + 1
            if minute >= 60:
                minute -= 60
                hour += 1
            if hour >= 24:
                hour = 0

            logger.info(f"Sending WhatsApp to {phone} about property {match['property_id']}")

            # Send the WhatsApp message
            pywhatkit.sendwhatmsg(
                phone,
                message,
                hour,
                minute,
                wait_time=20,  # Wait 20 seconds for WhatsApp to open
                tab_close=True  # Close the tab after sending
            )

            # Mark notification as sent
            self._update_notification_status(match['id'], 'sent', 'whatsapp', message)

            logger.info(f"WhatsApp notification sent for match {match['id']}")
            return True
        except Exception as e:
            logger.error(f"Error sending WhatsApp notification: {e}")
            self._update_notification_status(match['id'], 'failed', 'whatsapp', str(e))
            return False

    def _update_notification_status(self, match_id, status, method, message):
        """Update notification status in database"""
        try:
            # First get the match details
            self.cursor.execute("SELECT client_id, property_id FROM client_matches WHERE id = ?", (match_id,))
            match_data = self.cursor.fetchone()

            if not match_data:
                return False

            # Update the match record
            self.cursor.execute('''
                UPDATE client_matches
                SET notification_sent = 1,
                    notification_date = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (match_id,))

            # Add to notifications table
            self.cursor.execute('''
                INSERT INTO notifications (
                    client_id, property_id, message, method, status
                ) VALUES (?, ?, ?, ?, ?)
            ''', (
                match_data['client_id'],
                match_data['property_id'],
                message,
                method,
                status
            ))

            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error updating notification status: {e}")
            return False

    def record_client_response(self, match_id, response):
        """Record client's response to a property match"""
        try:
            self.cursor.execute('''
                UPDATE client_matches
                SET client_response = ?
                WHERE id = ?
            ''', (response, match_id))

            self.conn.commit()
            logger.info(f"Recorded client response '{response}' for match {match_id}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Error recording client response: {e}")
            return False

    def schedule_meeting(self, match_id, meeting_date, notes=""):
        """Schedule a meeting between client and agent"""
        try:
            self.cursor.execute('''
                UPDATE client_matches
                SET meeting_scheduled = 1,
                    meeting_date = ?,
                    notes = ?
                WHERE id = ?
            ''', (meeting_date, notes, match_id))

            self.conn.commit()
            logger.info(f"Scheduled meeting for match {match_id} on {meeting_date}")
            return True
        except sqlite3.Error as e:
            logger.error(f"Error scheduling meeting: {e}")
            return False

    def get_upcoming_meetings(self):
        """Get upcoming meetings"""
        try:
            self.cursor.execute('''
                SELECT cm.*, c.name AS client_name, c.phone AS client_phone,
                       pl.title AS property_title, pl.location AS property_location
                FROM client_matches cm
                JOIN clients c ON cm.client_id = c.id
                JOIN property_leads pl ON cm.property_id = pl.id
                WHERE cm.meeting_scheduled = 1
                AND cm.meeting_date >= datetime('now')
                ORDER BY cm.meeting_date
            ''')

            meetings = [dict(row) for row in self.cursor.fetchall()]
            return meetings
        except sqlite3.Error as e:
            logger.error(f"Error getting upcoming meetings: {e}")
            return []

    def send_notifications_batch(self, min_score=70):
        """Send notifications for all unnotified matches"""
        matches = self.get_unnotified_matches(min_score)

        if not matches:
            logger.info("No unnotified matches found")
            return 0

        sent_count = 0
        for match in matches:
            # Currently only supporting WhatsApp
            if whatsapp_available and match['client_phone']:
                if self.send_whatsapp_notification(match):
                    sent_count += 1
                    # Add some delay between sends
                    time.sleep(random.uniform(3, 5))

        logger.info(f"Sent {sent_count} match notifications")
        return sent_count

    def show_statistics(self):
        """Show database statistics"""
        try:
            stats = {}

            # Count properties
            self.cursor.execute("SELECT COUNT(*) FROM property_leads")
            stats['property_count'] = self.cursor.fetchone()[0]

            # Count clients
            self.cursor.execute("SELECT COUNT(*) FROM clients")
            stats['client_count'] = self.cursor.fetchone()[0]

            # Count matches
            self.cursor.execute("SELECT COUNT(*) FROM client_matches")
            stats['match_count'] = self.cursor.fetchone()[0]

            # Count notifications sent
            self.cursor.execute("SELECT COUNT(*) FROM client_matches WHERE notification_sent = 1")
            stats['notifications_sent'] = self.cursor.fetchone()[0]

            # Count scheduled meetings
            self.cursor.execute("SELECT COUNT(*) FROM client_matches WHERE meeting_scheduled = 1")
            stats['meetings_scheduled'] = self.cursor.fetchone()[0]

            return stats
        except sqlite3.Error as e:
            logger.error(f"Error getting statistics: {e}")
            return {}

    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")


# CLI menu for the system
def main():
    print("\n===== Real Estate Client Matching System =====")

    # Get database path
    db_path = input("Enter database path (or press Enter for default 'database.db'): ")
    if not db_path:
        db_path = "database.db"

    system = ClientMatchingSystem(db_path)

    while True:
        print("\nMain Menu:")
        print("1. Client Management")
        print("2. View Properties")
        print("3. Matching & Notifications")
        print("4. Meetings & Follow-ups")
        print("5. Show Statistics")
        print("0. Exit")

        choice = input("\nEnter your choice (0-5): ")

        if choice == '1':
            client_menu(system)
        elif choice == '2':
            property_menu(system)
        elif choice == '3':
            matching_menu(system)
        elif choice == '4':
            meeting_menu(system)
        elif choice == '5':
            show_statistics(system)
        elif choice == '0':
            system.close()
            print("\nThank you for using the system. Goodbye!")
            break
        else:
            print("\nInvalid choice. Please try again.")


def client_menu(system):
    while True:
        print("\n----- Client Management -----")
        print("1. Add New Client")
        print("2. View All Clients")
        print("3. Edit Client")
        print("4. Delete Client")
        print("0. Back to Main Menu")

        choice = input("\nEnter your choice (0-4): ")

        if choice == '1':
            # Add new client
            print("\n--- Add New Client ---")
            name = input("Client Name: ")
            phone = input("Phone Number (with country code, e.g. +923001234567): ")
            email = input("Email (optional): ")
            location = input("Preferred Location: ")

            # Get size requirements
            min_size = input("Minimum Size (numeric value): ")
            max_size = input("Maximum Size (numeric value, optional): ")
            size_unit = input("Size Unit (marla/kanal): ") or "marla"

            # Get budget
            min_budget = input("Minimum Budget (PKR): ")
            max_budget = input("Maximum Budget (PKR): ")

            requirements = input("Additional Requirements: ")

            client_data = {
                'name': name,
                'phone': phone,
                'email': email,
                'preferred_location': location,
                'min_size': float(min_size) if min_size else 0,
                'max_size': float(max_size) if max_size else None,
                'size_unit': size_unit,
                'min_budget': float(min_budget) if min_budget else 0,
                'max_budget': float(max_budget) if max_budget else None,
                'requirements': requirements,
                'status': 'active'
            }

            client_id = system.add_client(client_data)
            if client_id:
                print(f"\nClient added successfully with ID: {client_id}")
                # Show matches immediately
                matches = system.get_client_matches(client_id)
                if matches:
                    print(f"\nFound {len(matches)} potential property matches:")
                    for i, match in enumerate(matches[:5]):  # Show top 5
                        print(f"{i + 1}. {match['title']} - {match['price']} - Match: {match['match_score']:.1f}%")
            else:
                print("\nFailed to add client.")

        elif choice == '2':
            # View all clients
            clients = system.get_all_clients()
            if not clients:
                print("\nNo clients found in database.")
            else:
                print(f"\n--- All Clients ({len(clients)}) ---")
                for client in clients:
                    print(
                        f"ID: {client['id']} | {client['name']} | {client['phone']} | {client['preferred_location']} | Budget: {client['min_budget']}-{client['max_budget']}")

        elif choice == '3':
            # Edit client
            client_id = input("\nEnter Client ID to edit: ")
            if not client_id.isdigit():
                print("Invalid ID. Please enter a number.")
                continue

            client = system.get_client(int(client_id))
            if not client:
                print(f"Client with ID {client_id} not found.")
                continue

            print(f"\nEditing Client: {client['name']} (ID: {client['id']})")
            print("(Press Enter to keep current values)")

            name = input(f"Name [{client['name']}]: ") or client['name']
            phone = input(f"Phone [{client['phone']}]: ") or client['phone']
            email = input(f"Email [{client['email']}]: ") or client['email']
            location = input(f"Location [{client['preferred_location']}]: ") or client['preferred_location']
            min_size = input(f"Min Size [{client['min_size']}]: ")
            max_size = input(f"Max Size [{client['max_size']}]: ")
            size_unit = input(f"Size Unit [{client['size_unit']}]: ") or client['size_unit']
            min_budget = input(f"Min Budget [{client['min_budget']}]: ")
            max_budget = input(f"Max Budget [{client['max_budget']}]: ")
            requirements = input(f"Requirements [{client['requirements']}]: ") or client['requirements']

            client_data = {
                'name': name,
                'phone': phone,
                'email': email,
                'preferred_location': location,
                'min_size': float(min_size) if min_size else client['min_size'],
                'max_size': float(max_size) if max_size else client['max_size'],
                'size_unit': size_unit,
                'min_budget': float(min_budget) if min_budget else client['min_budget'],
                'max_budget': float(max_budget) if max_budget else client['max_budget'],
                'requirements': requirements,
            }

            if system.update_client(int(client_id), client_data):
                print(f"\nClient {client_id} updated successfully.")
                # Show new matches
                matches = system.get_client_matches(int(client_id))
                if matches:
                    print(f"\nFound {len(matches)} potential property matches:")
                    for i, match in enumerate(matches[:5]):  # Show top 5
                        print(f"{i + 1}. {match['title']} - {match['price']} - Match: {match['match_score']:.1f}%")
            else:
                print(f"\nFailed to update client {client_id}.")

        elif choice == '4':
            # Delete client
            client_id = input("\nEnter Client ID to delete: ")
            if not client_id.isdigit():
                print("Invalid ID. Please enter a number.")
                continue

            confirm = input(f"Are you sure you want to delete client {client_id}? (y/n): ")
            if confirm.lower() == 'y':
                if system.delete_client(int(client_id)):
                    print(f"\nClient {client_id} deleted successfully.")
                else:
                    print(f"\nFailed to delete client {client_id}.")
            else:
                print("Deletion cancelled.")

        elif choice == '0':
            break
        else:
            print("\nInvalid choice. Please try again.")


def property_menu(system):
    while True:
        print("\n----- Property Management -----")
        print("1. View All Properties")
        print("2. Search Properties")
        print("3. View Property Details")
        print("0. Back to Main Menu")

        choice = input("\nEnter your choice (0-3): ")

        if choice == '1':
            # View all properties
            try:
                system.cursor.execute("""
                    SELECT * FROM property_leads 
                    ORDER BY id DESC
                    LIMIT 50
                """)
                properties = system.cursor.fetchall()

                if not properties:
                    print("\nNo properties found in database.")
                else:
                    print(f"\n--- Available Properties (showing first 50) ---")
                    for prop in properties:
                        print(
                            f"ID: {prop['id']} | {prop['title']} | {prop['location']} | {prop['price']} | {prop['size']}")
            except sqlite3.Error as e:
                print(f"Database error: {e}")

        elif choice == '2':
            # Search properties
            search_term = input("\nEnter search term (location, size, price): ")

            try:
                system.cursor.execute("""
                    SELECT * FROM property_leads 
                    WHERE title LIKE ? OR location LIKE ? OR price LIKE ? OR size LIKE ?
                    ORDER BY id DESC
                    LIMIT 30
                """, (f'%{search_term}%', f'%{search_term}%', f'%{search_term}%', f'%{search_term}%'))

                properties = system.cursor.fetchall()

                if not properties:
                    print("\nNo matching properties found.")
                else:
                    print(f"\n--- Search Results ({len(properties)} properties) ---")
                    for prop in properties:
                        print(
                            f"ID: {prop['id']} | {prop['title']} | {prop['location']} | {prop['price']} | {prop['size']}")
            except sqlite3.Error as e:
                print(f"Database error: {e}")

        elif choice == '3':
            # View property details
            property_id = input("\nEnter Property ID: ")
            if not property_id.isdigit():
                print("Invalid ID. Please enter a number.")
                continue

            try:
                system.cursor.execute("SELECT * FROM property_leads WHERE id = ?", (property_id,))
                prop = system.cursor.fetchone()

                if not prop:
                    print(f"\nProperty with ID {property_id} not found.")
                else:
                    print(f"\n--- Property Details (ID: {prop['id']}) ---")
                    print(f"Title: {prop['title']}")
                    print(f"Location: {prop['location']}")
                    print(f"Price: {prop['price']}")
                    print(f"Size: {prop['size']}")
                    print(f"Property Type: {prop['property_type']}")
                    print(f"Description: {prop['description']}")
                    print(f"Seller: {prop['seller_name']}")
                    print(f"Contact: {prop['contact_number']}")
                    print(f"Source: {prop['source']}")
                    print(f"Status: {prop['status']}")

                    # Show clients that match this property
                    system.cursor.execute("""
                        SELECT cm.*, c.name AS client_name, c.phone AS client_phone
                        FROM client_matches cm
                        JOIN clients c ON cm.client_id = c.id
                        WHERE cm.property_id = ?
                        ORDER BY cm.match_score DESC
                    """, (property_id,))

                    matches = system.cursor.fetchall()
                    if matches:
                        print(f"\nMatched with {len(matches)} clients:")
                        for match in matches:
                            print(
                                f"  - {match['client_name']} | {match['client_phone']} | Match: {match['match_score']:.1f}%")
                    else:
                        print("\nNo client matches found for this property.")
            except sqlite3.Error as e:
                print(f"Database error: {e}")

        elif choice == '0':
            break
        else:
            print("\nInvalid choice. Please try again.")


def matching_menu(system):
    while True:
        print("\n----- Matching & Notifications -----")
        print("1. Find Matches for Client")
        print("2. View All Matches")
        print("3. View Client's Matches")
        print("4. Send Match Notifications")
        print("5. View Notification History")
        print("0. Back to Main Menu")

        choice = input("\nEnter your choice (0-5): ")

        if choice == '1':
            # Find matches for client
            client_id = input("\nEnter Client ID: ")
            if not client_id.isdigit():
                print("Invalid ID. Please enter a number.")
                continue

            matches = system.find_matches_for_client(int(client_id))

            if matches:
                print(f"\nFound {len(matches)} potential property matches:")
                for i, match in enumerate(matches):
                    print(f"{i + 1}. Property ID: {match['property_id']} | Match Score: {match['match_score']:.1f}%")
            else:
                print("\nNo matching properties found for this client.")

        elif choice == '2':
            # View all matches
            matches = system.get_all_matches()

            if not matches:
                print("\nNo matches found in database.")
            else:
                print(f"\n--- All Client-Property Matches ({len(matches)}) ---")
                for match in matches:
                    notified = "✓ Notified" if match['notification_sent'] == 1 else "Not notified"
                    print(
                        f"Match ID: {match['id']} | Client: {match['client_name']} | Property: {match['property_title']} | Score: {match['match_score']:.1f}% | {notified}")

        elif choice == '3':
            # View client's matches
            client_id = input("\nEnter Client ID: ")
            if not client_id.isdigit():
                print("Invalid ID. Please enter a number.")
                continue

            matches = system.get_client_matches(int(client_id))

            if not matches:
                print("\nNo matches found for this client.")
            else:
                print(f"\n--- Client {client_id} Matches ({len(matches)}) ---")
                for i, match in enumerate(matches):
                    notified = "✓ Notified" if match.get('notification_sent', 0) == 1 else "Not notified"
                    print(
                        f"{i + 1}. {match['title']} | {match['price']} | {match['location']} | Score: {match['match_score']:.1f}% | {notified}")

        elif choice == '4':
            # Send notifications
            print("\n--- Send Match Notifications ---")
            min_score = input("Minimum match score to notify (default: 70): ") or "70"
            if not min_score.replace('.', '', 1).isdigit():
                print("Invalid score. Please enter a number.")
                continue

            confirm = input(f"Send notifications for all unnotified matches with score >= {min_score}%? (y/n): ")
            if confirm.lower() == 'y':
                print("\nPreparing to send notifications...")
                if whatsapp_available:
                    print("WhatsApp Web will open in your browser. Please scan the QR code if prompted.")
                    print("Note: Multiple browser windows may open if there are multiple notifications.")

                    count = system.send_notifications_batch(float(min_score))
                    print(f"\nSent {count} notifications successfully.")
                else:
                    print("\nWhatsApp is not available. Please install pywhatkit package:")
                    print("  pip install pywhatkit")
            else:
                print("Notification sending cancelled.")

        elif choice == '5':
            # View notification history
            try:
                system.cursor.execute("""
                    SELECT n.*, c.name AS client_name, pl.title AS property_title,
                           n.sent_date, n.method, n.status
                    FROM notifications n
                    JOIN clients c ON n.client_id = c.id
                    JOIN property_leads pl ON n.property_id = pl.id
                    ORDER BY n.sent_date DESC
                    LIMIT 20
                """)

                notifications = system.cursor.fetchall()

                if not notifications:
                    print("\nNo notification history found.")
                else:
                    print(f"\n--- Recent Notifications (showing last 20) ---")
                    for notif in notifications:
                        sent_date = notif['sent_date']
                        print(
                            f"{sent_date} | {notif['method'].upper()} | To: {notif['client_name']} | Property: {notif['property_title']} | Status: {notif['status']}")
            except sqlite3.Error as e:
                print(f"Database error: {e}")

        elif choice == '0':
            break
        else:
            print("\nInvalid choice. Please try again.")


def meeting_menu(system):
    while True:
        print("\n----- Meetings & Follow-ups -----")
        print("1. Record Client Response")
        print("2. Schedule Meeting")
        print("3. View Upcoming Meetings")
        print("4. View Client Responses")
        print("0. Back to Main Menu")

        choice = input("\nEnter your choice (0-4): ")

        if choice == '1':
            # Record client response
            match_id = input("\nEnter Match ID: ")
            if not match_id.isdigit():
                print("Invalid ID. Please enter a number.")
                continue

            print("\nResponse options:")
            print("1. Interested - Client wants more info / viewing")
            print("2. Not Interested - Client rejected this property")
            print("3. No Response - Client didn't respond")

            resp_choice = input("\nEnter response type (1-3): ")

            response = None
            if resp_choice == '1':
                response = "interested"
            elif resp_choice == '2':
                response = "not_interested"
            elif resp_choice == '3':
                response = "no_response"
            else:
                print("Invalid response type.")
                continue

            if system.record_client_response(int(match_id), response):
                print(f"\nClient response recorded as '{response}'")

                # If interested, suggest scheduling a meeting
                if response == "interested":
                    schedule = input("\nWould you like to schedule a meeting now? (y/n): ")
                    if schedule.lower() == 'y':
                        meeting_date = input("Meeting Date (YYYY-MM-DD HH:MM): ")
                        notes = input("Meeting Notes: ")

                        if system.schedule_meeting(int(match_id), meeting_date, notes):
                            print(f"\nMeeting scheduled for {meeting_date}")
                        else:
                            print("\nFailed to schedule meeting.")
            else:
                print("\nFailed to record client response.")

        elif choice == '2':
            # Schedule meeting
            match_id = input("\nEnter Match ID: ")
            if not match_id.isdigit():
                print("Invalid ID. Please enter a number.")
                continue

            meeting_date = input("Meeting Date (YYYY-MM-DD HH:MM): ")
            notes = input("Meeting Notes: ")

            if system.schedule_meeting(int(match_id), meeting_date, notes):
                print(f"\nMeeting scheduled for {meeting_date}")
            else:
                print("\nFailed to schedule meeting.")

        elif choice == '3':
            # View upcoming meetings
            meetings = system.get_upcoming_meetings()

            if not meetings:
                print("\nNo upcoming meetings scheduled.")
            else:
                print(f"\n--- Upcoming Meetings ({len(meetings)}) ---")
                for meeting in meetings:
                    print(
                        f"Match ID: {meeting['id']} | Date: {meeting['meeting_date']} | Client: {meeting['client_name']} | Property: {meeting['property_title']}")

        elif choice == '4':
            # View client responses
            try:
                system.cursor.execute("""
                    SELECT cm.id, cm.client_response, c.name AS client_name, 
                           pl.title AS property_title, cm.notification_date
                    FROM client_matches cm
                    JOIN clients c ON cm.client_id = c.id
                    JOIN property_leads pl ON cm.property_id = pl.id
                    WHERE cm.notification_sent = 1
                    AND cm.client_response IS NOT NULL
                    ORDER BY cm.notification_date DESC
                """)

                responses = system.cursor.fetchall()

                if not responses:
                    print("\nNo client responses recorded.")
                else:
                    print(f"\n--- Client Responses ({len(responses)}) ---")
                    for resp in responses:
                        print(
                            f"Match ID: {resp['id']} | Client: {resp['client_name']} | Property: {resp['property_title']} | Response: {resp['client_response']}")
            except sqlite3.Error as e:
                print(f"Database error: {e}")

        elif choice == '0':
            break
        else:
            print("\nInvalid choice. Please try again.")


def show_statistics(system):
    """Show system statistics"""
    stats = system.show_statistics()

    if not stats:
        print("\nCouldn't retrieve statistics.")
        return

    print("\n===== System Statistics =====")
    print(f"Total Properties: {stats['property_count']}")
    print(f"Total Clients: {stats['client_count']}")
    print(f"Total Matches: {stats['match_count']}")
    print(f"Notifications Sent: {stats['notifications_sent']}")
    print(f"Meetings Scheduled: {stats['meetings_scheduled']}")

    # Calculate success rates
    if stats['match_count'] > 0:
        notification_rate = (stats['notifications_sent'] / stats['match_count']) * 100
        print(f"Notification Rate: {notification_rate:.1f}%")

    if stats['notifications_sent'] > 0:
        meeting_rate = (stats['meetings_scheduled'] / stats['notifications_sent']) * 100
        print(f"Meeting Conversion Rate: {meeting_rate:.1f}%")

    input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()