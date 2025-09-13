import pywhatkit
import time
import sqlite3
import logging
import random
from datetime import datetime, timedelta
from database_operations import DatabaseManager, get_db_path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('whatsapp_sender.log'), logging.StreamHandler()]
)
logger = logging.getLogger('whatsapp_sender')

class WhatsAppLeadSender:
    """Class to send property leads via WhatsApp"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.agent_numbers = []
        self.load_agent_numbers()
        
    def load_agent_numbers(self):
        """Load agent WhatsApp numbers from database or config"""
        # You can extend this to load from a database table
        # For now, we'll use a simple list
        self.agent_numbers = [
            "+923001234567",  # Replace with your actual agent numbers
            "+923009876543"   # Add all your agent numbers here
        ]
        logger.info(f"Loaded {len(self.agent_numbers)} agent numbers")
        
    def format_lead_message(self, lead):
        """Format a WhatsApp message for a property lead"""
        message = f"*NEW PROPERTY LEAD*\n\n"
        message += f"*{lead['title']}*\n\n"
        
        # Add price if available
        if lead['price'] and lead['price'].lower() != 'n/a':
            message += f"*Price:* {lead['price']}\n"
            
        # Add location
        message += f"*Location:* {lead['location']}\n"
        
        # Add size if available
        if lead['size'] and lead['size'].lower() != 'n/a':
            message += f"*Size:* {lead['size']}\n"
        
        # Add urgency level
        urgency_emoji = "🔴" if lead['urgency'] == "HIGH" else "🟠" if lead['urgency'] == "MEDIUM" else "🟢"
        message += f"*Urgency:* {urgency_emoji} {lead['urgency']}\n\n"
        
        # Add contact info if available
        if lead['contact_number'] and lead['contact_number'].lower() != 'contact through olx' and lead['contact_number'].lower() != 'contact through zameen.com':
            message += f"*Contact:* {lead['contact_number']}\n"
            
        if lead['seller_name'] and lead['seller_name'].lower() != 'n/a':
            message += f"*Seller:* {lead['seller_name']}\n"
            
        # Add listing URL
        message += f"\n*Listing:* {lead['listing_url']}\n"
        
        # Add description (shortened)
        desc = lead['description']
        if len(desc) > 100:
            desc = desc[:97] + "..."
        message += f"\n{desc}\n"
        
        # Add source and timestamp
        message += f"\n*Source:* {lead['source']}"
        message += f"\n*Sent:* {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
        return message
    
    def send_lead_via_whatsapp(self, lead, agent_number):
        """Send a single lead to an agent via WhatsApp"""
        try:
            # Format the message
            message = self.format_lead_message(lead)
            
            # Get current time for scheduling (pywhatkit needs this)
            now = datetime.now()
            
            # Schedule message to be sent 1 minute from now
            # This gives time for WhatsApp Web to open and connect
            send_time = now + timedelta(minutes=1)
            hour = send_time.hour
            minute = send_time.minute
            
            logger.info(f"Scheduling WhatsApp message for lead ID {lead['id']} to {agent_number}")
            
            # Send the WhatsApp message
            # This will open WhatsApp Web in a browser
            pywhatkit.sendwhatmsg(
                agent_number,
                message,
                hour,
                minute,
                wait_time=20,  # Wait 20 seconds for WhatsApp to open
                tab_close=True  # Close the tab after sending
            )
            
            logger.info(f"WhatsApp message sent for lead ID {lead['id']} to {agent_number}")
            
            # Update database to mark this lead as sent to this agent
            self.db.mark_lead_sent_to_agent(lead['id'], agent_number)
            
            # Wait a bit before sending the next message to avoid rate limiting
            time.sleep(random.randint(3, 8))
            
            return True
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message for lead ID {lead['id']}: {e}")
            return False
    
    def distribute_leads_to_agents(self, leads=None, send_all=False):
        """Distribute leads to agents based on rules"""
        if not self.agent_numbers:
            logger.error("No agent numbers available. Cannot distribute leads.")
            return 0
        
        # Get unsent leads if not provided
        if leads is None:
            leads = self.db.get_unsent_leads() if not send_all else self.db.get_all_leads()
        
        if not leads:
            logger.info("No new leads to distribute")
            return 0
        
        logger.info(f"Distributing {len(leads)} leads to {len(self.agent_numbers)} agents")
        
        sent_count = 0
        
        # Distribute leads
        for i, lead in enumerate(leads):
            # Simple round-robin distribution
            agent_index = i % len(self.agent_numbers)
            agent_number = self.agent_numbers[agent_index]
            
            # Prioritize high urgency leads to all agents
            if lead['urgency'] == "HIGH":
                logger.info(f"High urgency lead ID {lead['id']} - sending to all agents")
                for agent_number in self.agent_numbers:
                    success = self.send_lead_via_whatsapp(lead, agent_number)
                    if success:
                        sent_count += 1
            else:
                # Normal leads go to just one agent
                success = self.send_lead_via_whatsapp(lead, agent_number)
                if success:
                    sent_count += 1
        
        logger.info(f"Successfully distributed {sent_count} leads via WhatsApp")
        return sent_count

    def send_urgent_leads(self):
        """Send only urgent leads to all agents"""
        urgent_leads = self.db.get_urgent_leads()
        
        if not urgent_leads:
            logger.info("No urgent leads to send")
            return 0
            
        logger.info(f"Sending {len(urgent_leads)} urgent leads to all agents")
        
        sent_count = 0
        
        for lead in urgent_leads:
            for agent_number in self.agent_numbers:
                success = self.send_lead_via_whatsapp(lead, agent_number)
                if success:
                    sent_count += 1
                    
        logger.info(f"Successfully sent {sent_count} urgent leads")
        return sent_count
        
    def send_test_message(self, phone_number):
        """Send a test WhatsApp message to verify the system works"""
        try:
            # Get current time
            now = datetime.now()
            
            # Schedule message to be sent 1 minute from now
            hour = now.hour
            minute = now.minute + 1
            if minute >= 60:
                minute -= 60
                hour += 1
            
            # Send the test message
            test_message = "This is a test message from your Property Lead Management System. If you received this, WhatsApp integration is working correctly!"
            
            logger.info(f"Sending test WhatsApp message to {phone_number}")
            
            pywhatkit.sendwhatmsg(
                phone_number,
                test_message,
                hour,
                minute,
                wait_time=20,
                tab_close=True
            )
            
            logger.info("Test message sent successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to send test message: {e}")
            return False


if __name__ == "__main__":
    print("===== WhatsApp Lead Sender =====")
    
    sender = WhatsAppLeadSender()
    
    # Ask for mode
    print("\nSelect an option:")
    print("1. Send a test message")
    print("2. Send all unsent leads")
    print("3. Send only urgent leads")
    print("4. Send all leads")
    
    choice = input("\nEnter your choice (1-4): ")
    
    if choice == '1':
        # Send test message
        phone = input("\nEnter WhatsApp number with country code (e.g., +923001234567): ")
        print("\nPreparing to send test message...")
        print("WhatsApp Web will open in your browser. Please scan the QR code if prompted.")
        sender.send_test_message(phone)
        
    elif choice == '2':
        # Send unsent leads
        print("\nPreparing to send all unsent leads...")
        print("WhatsApp Web will open in your browser. Please scan the QR code if prompted.")
        count = sender.distribute_leads_to_agents()
        print(f"Sent {count} leads via WhatsApp")
        
    elif choice == '3':
        # Send urgent leads
        print("\nPreparing to send urgent leads...")
        print("WhatsApp Web will open in your browser. Please scan the QR code if prompted.")
        count = sender.send_urgent_leads()
        print(f"Sent {count} urgent leads via WhatsApp")
        
    elif choice == '4':
        # Send all leads
        print("\nPreparing to send all leads...")
        print("WhatsApp Web will open in your browser. Please scan the QR code if prompted.")
        count = sender.distribute_leads_to_agents(send_all=True)
        print(f"Sent {count} leads via WhatsApp")
        
    else:
        print("Invalid choice. Please run the script again.")