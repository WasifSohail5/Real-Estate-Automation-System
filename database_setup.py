import sqlite3
import os
import datetime

def get_db_path():
    """Returns the database file path"""
    # Current directory mein database file create karna
    current_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(current_dir, 'real_estate.db')
    return db_path

def setup_database():
    """Initial database setup with required tables"""
    conn = None
    try:
        conn = sqlite3.connect(get_db_path())
        cursor = conn.cursor()
        
        # Create property leads table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS property_leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            price TEXT,
            location TEXT,
            property_type TEXT,
            size TEXT,
            bedrooms INTEGER,
            bathrooms INTEGER,
            seller_name TEXT,
            contact_number TEXT,
            contact_email TEXT,
            source TEXT,
            listing_url TEXT,
            urgency TEXT DEFAULT 'NORMAL',
            status TEXT DEFAULT 'NEW',
            contacted INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Create communication history table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS communication_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER,
            communication_type TEXT,
            message_content TEXT,
            status TEXT,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (lead_id) REFERENCES property_leads (id)
        )
        ''')
        
        # Create settings table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            setting_name TEXT UNIQUE,
            setting_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # Insert default settings
        default_settings = [
            ('scraping_interval_hours', '3'),
            ('whatsapp_template_normal', 'Hello, I noticed your property listing for {title} at {location}. Is it still available?'),
            ('whatsapp_template_urgent', 'Hello, I am very interested in your urgent listing for {title} at {location}. Is it available for immediate viewing?'),
            ('email_template_subject', 'Regarding your property listing: {title}'),
            ('last_scrape_time', datetime.datetime.now().isoformat())
        ]
        
        for setting in default_settings:
            try:
                cursor.execute('INSERT OR IGNORE INTO settings (setting_name, setting_value) VALUES (?, ?)', setting)
            except sqlite3.IntegrityError:
                pass  # Skip if setting already exists
        
        conn.commit()
        print("Database setup successfully completed.")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    setup_database()