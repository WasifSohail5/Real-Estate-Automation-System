import sqlite3
import os
from database_setup import get_db_path


def clean_database():
    """Completely clean the database and reset it"""
    conn = None
    try:
        db_path = get_db_path()
        print(f"Connecting to database at: {db_path}")

        # Check if database exists
        if not os.path.exists(db_path):
            print("Database file doesn't exist. Nothing to clean.")
            return True

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        print("Starting complete database cleanup...")

        # Delete all entries from communication_history (due to foreign key constraints)
        cursor.execute("DELETE FROM communication_history")
        comm_deleted = cursor.rowcount
        print(f"Deleted {comm_deleted} communication records.")

        # Delete all entries from property_leads
        cursor.execute("DELETE FROM property_leads")
        leads_deleted = cursor.rowcount
        print(f"Deleted {leads_deleted} property leads.")

        # Reset auto-increment counters
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='property_leads' OR name='communication_history'")

        conn.commit()
        print("Database has been completely cleaned.")

        return True

    except sqlite3.Error as e:
        print(f"Database error during cleanup: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    clean_database()