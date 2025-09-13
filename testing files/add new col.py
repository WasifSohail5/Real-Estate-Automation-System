import sqlite3
from database_setup import get_db_path


def add_email_column():
    """Add email column to property_leads table"""
    conn = None
    try:
        db_path = get_db_path()
        print(f"Connecting to database at: {db_path}")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check if column already exists
        cursor.execute("PRAGMA table_info(property_leads)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]

        if 'email' not in column_names:
            print("Adding 'email' column to property_leads table...")
            cursor.execute("ALTER TABLE property_leads ADD COLUMN email TEXT")
            conn.commit()
            print("Column added successfully!")
        else:
            print("Email column already exists.")

        return True

    except sqlite3.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    print("This will add an 'email' column to your property_leads table.")
    confirm = input("Do you want to proceed? (y/n): ")

    if confirm.lower() == 'y':
        add_email_column()
    else:
        print("Operation cancelled.")