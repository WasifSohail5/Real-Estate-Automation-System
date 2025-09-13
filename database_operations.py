import sqlite3
import datetime
from database_setup import get_db_path

class DatabaseManager:
    def __init__(self):
        self.db_path = get_db_path()
    
    def _get_connection(self):
        """Get database connection"""
        return sqlite3.connect(self.db_path)
    
    def add_lead(self, lead_data):
        """Add a new property lead to the database"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Check if lead with same title and contact exists to avoid duplicates
            cursor.execute('''
                SELECT id FROM property_leads 
                WHERE title = ? AND contact_number = ? AND location = ?
            ''', (lead_data.get('title'), lead_data.get('contact_number'), lead_data.get('location')))
            
            existing = cursor.fetchone()
            if existing:
                print(f"Lead already exists with ID {existing[0]}")
                return existing[0]
            
            # Insert new lead
            columns = ', '.join(lead_data.keys())
            placeholders = ', '.join(['?' for _ in lead_data])
            
            query = f'''
                INSERT INTO property_leads ({columns}) 
                VALUES ({placeholders})
            '''
            
            cursor.execute(query, list(lead_data.values()))
            conn.commit()
            
            lead_id = cursor.lastrowid
            print(f"Added new lead with ID {lead_id}")
            return lead_id
            
        except sqlite3.Error as e:
            print(f"Error adding lead: {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                conn.close()
    
    def get_leads(self, filters=None, limit=50):
        """Get property leads with optional filters"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            query = "SELECT * FROM property_leads"
            params = []
            
            if filters:
                conditions = []
                for key, value in filters.items():
                    conditions.append(f"{key} = ?")
                    params.append(value)
                
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
            
            query += f" ORDER BY created_at DESC LIMIT {limit}"
            
            cursor.execute(query, params)
            columns = [column[0] for column in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            return results
            
        except sqlite3.Error as e:
            print(f"Error fetching leads: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def get_lead_by_id(self, lead_id):
        """Get a specific lead by ID"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT * FROM property_leads WHERE id = ?", (lead_id,))
            columns = [column[0] for column in cursor.description]
            row = cursor.fetchone()
            
            if row:
                return dict(zip(columns, row))
            return None
            
        except sqlite3.Error as e:
            print(f"Error fetching lead: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def update_lead(self, lead_id, update_data):
        """Update an existing lead"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            set_clause = ', '.join([f"{key} = ?" for key in update_data.keys()])
            update_data['updated_at'] = datetime.datetime.now().isoformat()
            
            query = f'''
                UPDATE property_leads 
                SET {set_clause}, updated_at = ?
                WHERE id = ?
            '''
            
            values = list(update_data.values()) + [update_data['updated_at'], lead_id]
            cursor.execute(query, values)
            conn.commit()
            
            return cursor.rowcount > 0
            
        except sqlite3.Error as e:
            print(f"Error updating lead: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    def mark_lead_contacted(self, lead_id):
        """Mark a lead as contacted"""
        return self.update_lead(lead_id, {'contacted': 1, 'status': 'CONTACTED'})
    
    def add_communication(self, lead_id, comm_type, message, status="SENT"):
        """Record communication with a lead"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO communication_history 
                (lead_id, communication_type, message_content, status)
                VALUES (?, ?, ?, ?)
            ''', (lead_id, comm_type, message, status))
            
            conn.commit()
            return cursor.lastrowid
            
        except sqlite3.Error as e:
            print(f"Error recording communication: {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                conn.close()
    
    def get_communications_for_lead(self, lead_id):
        """Get all communications for a specific lead"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT * FROM communication_history
                WHERE lead_id = ?
                ORDER BY sent_at DESC
            ''', (lead_id,))
            
            columns = [column[0] for column in cursor.description]
            results = []
            
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            return results
            
        except sqlite3.Error as e:
            print(f"Error fetching communications: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def get_setting(self, setting_name):
        """Get a setting value by name"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT setting_value FROM settings
                WHERE setting_name = ?
            ''', (setting_name,))
            
            result = cursor.fetchone()
            return result[0] if result else None
            
        except sqlite3.Error as e:
            print(f"Error fetching setting: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def update_setting(self, setting_name, setting_value):
        """Update a setting value"""
        conn = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO settings 
                (setting_name, setting_value, updated_at)
                VALUES (?, ?, ?)
            ''', (setting_name, setting_value, datetime.datetime.now().isoformat()))
            
            conn.commit()
            return True
            
        except sqlite3.Error as e:
            print(f"Error updating setting: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                conn.close()
    
    def get_urgent_leads(self, limit=10):
        """Get high urgency leads that haven't been contacted"""
        return self.get_leads(
            filters={'urgency': 'HIGH', 'contacted': 0},
            limit=limit
        )