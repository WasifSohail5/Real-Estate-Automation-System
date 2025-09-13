import sqlite3
import logging
import asyncio
import os
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

# Import functions from our other modules
from property_match_notify import (
    parse_size, standardize_size, parse_price, find_matches_for_client,
    send_match_email, log_match_to_db, save_matches_to_file
)
from reply_handler_Version5 import (
    EmailResponseHandler
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("real-estate-api")

# Database path
DB_PATH = r"E:\BSAI-5th\DataMining\Real_State_Automation\real_estate.db"

# Create FastAPI app
app = FastAPI(
    title="Real Estate Automation API",
    description="API for property matching and automated email responses",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


# Database connection helper - thread safe
def get_db():
    """Get a new database connection (thread safe)"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# Ensure contact_email is set for all property leads
def update_property_contact_email():
    """Update all property leads to set contact_email where it's null"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Check if contact_email column exists, if not add it
        cursor.execute("PRAGMA table_info(property_leads)")
        columns = cursor.fetchall()
        column_names = [column['name'] for column in columns]

        # Add necessary columns if they don't exist
        if 'contact_email' not in column_names:
            cursor.execute("ALTER TABLE property_leads ADD COLUMN contact_email TEXT")

        if 'contact_number' not in column_names:
            cursor.execute("ALTER TABLE property_leads ADD COLUMN contact_number TEXT")

        if 'video_links' not in column_names:
            cursor.execute("ALTER TABLE property_leads ADD COLUMN video_links TEXT")

        # Update all records with null contact_email
        cursor.execute("""
            UPDATE property_leads 
            SET contact_email = 'zuberipersonal@gmail.com' 
            WHERE contact_email IS NULL OR contact_email = ''
        """)

        # Set default contact number if null
        cursor.execute("""
            UPDATE property_leads 
            SET contact_number = '+923197757134' 
            WHERE contact_number IS NULL OR contact_number = ''
        """)

        conn.commit()
        logger.info(f"Updated property leads with default contact information")
    except Exception as e:
        logger.error(f"Error updating property contact information: {e}")
    finally:
        conn.close()


# Call this function on startup
@app.on_event("startup")
async def startup_event():
    """Run on app startup"""
    logger.info("API server started successfully")
    update_property_contact_email()


# Models
class ClientBase(BaseModel):
    id: int
    name: str
    email: str
    min_budget: float
    max_budget: float
    min_size: float
    max_size: float
    size_unit: str
    preferred_location: str = None
    status: str = "active"


class PropertyBase(BaseModel):
    id: int
    title: str
    description: str
    price: str
    size: str
    location: str
    contact_email: str = None
    contact_number: str = None
    video_links: str = None


class MatchResponse(BaseModel):
    client_id: int
    property_id: int
    match_score: float
    email_sent: bool


class ProcessResponse(BaseModel):
    status: str
    message: str
    timestamp: str


# Routes
@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Real Estate Automation API", "status": "online"}


@app.post("/run-full-process/", response_model=ProcessResponse)
async def run_full_process(background_tasks: BackgroundTasks):
    """Run the full property matching and email reply handling process"""
    logger.info("Starting full process run")

    # Run email response handler to check for replies
    background_tasks.add_task(check_email_replies)

    return {
        "status": "success",
        "message": "Full process started in background",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


@app.post("/match-properties/", response_model=List[Dict[str, Any]])
async def match_properties(background_tasks: BackgroundTasks):
    """Match properties for all active clients and send emails"""
    background_tasks.add_task(run_property_matching)

    return {
        "status": "success",
        "message": "Property matching started in background",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


@app.post("/check-replies/", response_model=ProcessResponse)
async def check_replies(background_tasks: BackgroundTasks):
    """Check for email replies and handle interested clients"""
    background_tasks.add_task(check_email_replies)

    return {
        "status": "success",
        "message": "Email reply checking started in background",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


@app.get("/clients/", response_model=List[ClientBase])
async def get_clients(conn: sqlite3.Connection = Depends(get_db)):
    """Get all clients"""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM clients_data")
    clients = cursor.fetchall()

    # Convert to list of dicts
    return [dict(client) for client in clients]


@app.get("/properties/", response_model=List[PropertyBase])
async def get_properties(conn: sqlite3.Connection = Depends(get_db)):
    """Get all properties"""
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM property_leads")
    properties = cursor.fetchall()

    # Convert to list of dicts
    return [dict(prop) for prop in properties]


# Background tasks
async def run_property_matching():
    """Run property matching in the background"""
    conn = None
    try:
        # Create a new connection specifically for this background task
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='clients_data'")
        if not cursor.fetchone():
            logger.error("Error: clients_data table not found in database")
            return

        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='property_leads'")
        if not cursor.fetchone():
            logger.error("Error: property_leads table not found in database")
            return

        # Get all active clients
        cursor.execute("SELECT * FROM clients_data WHERE status = 'active'")
        clients = cursor.fetchall()

        logger.info(f"Found {len(clients)} active clients")

        # Process each client
        for client in clients:
            logger.info(f"Processing client: {client['name']} (ID: {client['id']})")

            # Find matching properties
            matches = find_matches_for_client(client, conn)

            if matches:
                logger.info(f"Found {len(matches)} matching properties for {client['name']}")

                # Try to send email notification
                email_sent = send_match_email(client, matches)

                # If email fails, save matches to file
                if not email_sent:
                    logger.info(f"Saving matches to file for {client['name']}...")
                    save_matches_to_file(client, matches)

                # Log matches to database
                for match in matches:
                    log_match_to_db(conn, client['id'], match['id'], match['match_score'], email_sent)
            else:
                logger.info(f"No matching properties found for {client['name']}")

        logger.info("Property matching and notification process completed")

    except Exception as e:
        logger.error(f"Error in property matching: {e}")
    finally:
        if conn:
            conn.close()


async def check_email_replies():
    """Check for email replies in the background"""
    handler = None
    try:
        # Create new handler instance (with its own DB connection)
        handler = EmailResponseHandler()
        handler.check_email_replies()
    except Exception as e:
        logger.error(f"Error checking email replies: {e}")
    finally:
        if handler:
            handler.close()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8005, reload=True)