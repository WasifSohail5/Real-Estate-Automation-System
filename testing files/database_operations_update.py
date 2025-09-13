# Add this method to your existing DatabaseManager class

def mark_lead_sent_to_agent(self, lead_id, agent_number):
    """Mark a lead as sent to a specific agent"""
    try:
        # Check if we already have a lead_agents table, if not create it
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS lead_agents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lead_id INTEGER,
                agent_number TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(lead_id, agent_number)
            )
        ''')
        self.conn.commit()
        
        # Insert the record
        self.cursor.execute('''
            INSERT OR IGNORE INTO lead_agents (lead_id, agent_number)
            VALUES (?, ?)
        ''', (lead_id, agent_number))
        self.conn.commit()
        
        # Update the lead status
        self.cursor.execute('''
            UPDATE property_leads 
            SET status = 'sent' 
            WHERE id = ?
        ''', (lead_id,))
        self.conn.commit()
        
        return True
    except Exception as e:
        print(f"Error marking lead as sent: {e}")
        return False

def get_unsent_leads(self):
    """Get leads that haven't been sent to agents"""
    try:
        self.cursor.execute('''
            SELECT p.* FROM property_leads p
            LEFT JOIN (
                SELECT DISTINCT lead_id FROM lead_agents
            ) la ON p.id = la.lead_id
            WHERE la.lead_id IS NULL
            ORDER BY 
                CASE 
                    WHEN p.urgency = 'HIGH' THEN 1
                    WHEN p.urgency = 'MEDIUM' THEN 2
                    ELSE 3
                END
        ''')
        
        columns = [description[0] for description in self.cursor.description]
        leads = []
        
        for row in self.cursor.fetchall():
            lead = dict(zip(columns, row))
            leads.append(lead)
            
        return leads
    except Exception as e:
        print(f"Error getting unsent leads: {e}")
        return []