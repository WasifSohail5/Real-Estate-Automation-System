import sqlite3
import os
from datetime import datetime


def add_clients_table(db_path=r"E:\BSAI-5th\DataMining\Real_State_Automation\real_estate.db"):
    """
    Add clients table to existing database and populate with clients
    """
    # Connect to existing database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create clients table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clients_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            preferred_location TEXT,
            min_size REAL,
            max_size REAL,
            size_unit TEXT DEFAULT 'marla',
            min_budget REAL,
            max_budget REAL,
            requirements TEXT,
            status TEXT DEFAULT 'active',
            added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Check if clients already exist
    cursor.execute("SELECT COUNT(*) FROM clients_data")
    client_count = cursor.fetchone()[0]

    if client_count == 0:
        # Sample client data (3 clients)
        sample_clients = [
            {
                'name': 'Wasif',
                'phone': '+923139379987',
                'email': 'wasifsohail456@gmail.com',
                'preferred_location': 'Bahria Town, Islamabad',
                'min_size': 5,
                'max_size': 8,
                'size_unit': 'marla',
                'min_budget': 2500000,  # 25 Lacs
                'max_budget': 8000000,  # 80 Lacs
                'requirements': 'Corner plot, near main road'
            },
            {
                'name': 'Qasim',
                'phone': '+923338971343',
                'email': 'qasimmustafa112@gmail.com',
                'preferred_location': 'DHA, Islamabad',
                'min_size': 10,
                'max_size': 20,
                'size_unit': 'marla',
                'min_budget': 10000000,  # 1 Crore
                'max_budget': 15000000,  # 1.5 Crore
                'requirements': 'Good location, developed area'
            },
            {
                'name': 'Faizan',
                'phone': '+923269800107',
                'email': 'mianfaizanalifaizi2004@gmail.com',
                'preferred_location': 'Faisal Town',
                'min_size': 1,
                'max_size': 2,
                'size_unit': 'kanal',
                'min_budget': 20000000,  # 2 Crore
                'max_budget': 30000000,  # 3 Crore
                'requirements': 'Residential plot in secure community'
            },
        ]

        # Insert sample clients
        for client in sample_clients:
            cursor.execute('''
                INSERT INTO clients_data (
                    name, phone, email, preferred_location,
                    min_size, max_size, size_unit,
                    min_budget, max_budget, requirements
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                client['name'],
                client['phone'],
                client['email'],
                client['preferred_location'],
                client['min_size'],
                client['max_size'],
                client['size_unit'],
                client['min_budget'],
                client['max_budget'],
                client['requirements']
            ))

        print(f"Added {len(sample_clients)} sample clients to database")
    else:
        print(f"Found {client_count} existing clients in database. No clients added.")

    # Commit changes
    conn.commit()

    # Display clients in database
    cursor.execute("SELECT id, name, phone, preferred_location, min_budget, max_budget FROM clients_data")
    clients = cursor.fetchall()

    print("\n=== Clients in Database ===")
    print("ID | Name | Phone | Location | Min Budget | Max Budget")
    print("-" * 80)
    for client in clients:
        min_budget_formatted = f"{client[4]:,}"
        max_budget_formatted = f"{client[5]:,}"
        print(
            f"{client[0]} | {client[1]} | {client[2]} | {client[3]} | Rs {min_budget_formatted} | Rs {max_budget_formatted}")

    # Close connection
    conn.close()

    print(f"\nClients table added successfully to database")


if __name__ == "__main__":
    # Update this to your actual database path if different
    add_clients_table(r"E:\BSAI-5th\DataMining\Real_State_Automation\real_estate.db")