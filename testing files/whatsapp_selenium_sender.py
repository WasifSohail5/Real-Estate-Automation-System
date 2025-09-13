from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import time
import logging
import urllib.parse
from database_operations import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('whatsapp_sender.log'), logging.StreamHandler()]
)
logger = logging.getLogger('whatsapp_selenium')

class WhatsAppSeleniumSender:
    """Class to send property leads via WhatsApp using Selenium"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.driver = None
        self.agent_numbers = []
        self.load_agent_numbers()
        self.setup_driver()
        
    def setup_driver(self):
        """Set up the Chrome WebDriver"""
        try:
            chrome_options = Options()
            # Uncomment this line if you want to run in headless mode
            # chrome_options.add_argument("--headless=new")
            
            # Add your user data directory to maintain WhatsApp session
            # chrome_options.add_argument("--user-data-dir=./whatsapp_profile")
            
            chrome_options.add_argument("--window-size=1280,800")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            
            # Add user-agent
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36")
            
            print("Setting up Chrome WebDriver for WhatsApp...")
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(30)
            print("WebDriver setup complete.")
        except Exception as e:
            logger.error(f"Error setting up Chrome WebDriver: {e}")
            print(f"Failed to set up WebDriver: {e}")
            raise
    
    def load_agent_numbers(self):
        """Load agent WhatsApp numbers from database or config"""
        # You can extend this to load from a database table
        # For now, we'll use a simple list
        self.agent_numbers = [
            "+923197757134",  # Replace with your actual agent numbers
            "+923338971343"   # Add all your agent numbers here
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
        message += f"\n{desc}"
        
        return message
    
    def send_whatsapp_message(self, phone_number, message):
        """Send a WhatsApp message using WhatsApp Web API URL"""
        try:
            # Format the phone number (remove any spaces, dashes, etc.)
            formatted_number = phone_number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
            
            # Encode the message for URL
            encoded_message = urllib.parse.quote(message)
            
            # Generate the WhatsApp API URL
            wa_url = f"https://web.whatsapp.com/send?phone={formatted_number}&text={encoded_message}"
            
            # Navigate to the WhatsApp URL
            logger.info(f"Opening WhatsApp Web for {phone_number}")
            self.driver.get(wa_url)
            
            # Wait for WhatsApp Web to load (this will require scanning QR code the first time)
            logger.info("Waiting for WhatsApp Web to load...")
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.XPATH, '//div[@contenteditable="true"]'))
            )
            
            # Wait for the message to be loaded in the input field
            time.sleep(3)
            
            # Click the send button
            logger.info("Clicking send button...")
            send_button = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//button[@data-testid="compose-btn-send"]'))
            )
            send_button.click()
            
            # Wait for the message to be sent
            logger.info("Waiting for message to be sent...")
            time.sleep(3)
            
            logger.info(f"Message sent successfully to {phone_number}")
            return True
        except TimeoutException:
            logger.error(f"Timeout waiting for WhatsApp Web to load for {phone_number}")
            # Capture screenshot for debugging
            self.driver.save_screenshot(f"whatsapp_timeout_{int(time.time())}.png")
            return False
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {e}")
            return False
    
    def send_lead_via_whatsapp(self, lead, agent_number):
        """Send a single lead to an agent via WhatsApp"""
        try:
            # Format the message
            message = self.format_lead_message(lead)
            
            # Send the message
            success = self.send_whatsapp_message(agent_number, message)
            
            if success:
                # Update database to mark this lead as sent
                self.db.mark_lead_sent_to_agent(lead['id'], agent_number)
                logger.info(f"Lead ID {lead['id']} marked as sent to {agent_number}")
            
            # Add delay between sends to avoid detection
            time.sleep(3)
            
            return success
        except Exception as e:
            logger.error(f"Error sending lead via WhatsApp: {e}")
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
        
        # Ensure WhatsApp Web is open and authenticated
        try:
            # First navigate to WhatsApp Web
            self.driver.get("https://web.whatsapp.com/")
            
            print("\n===== IMPORTANT =====")
            print("Please scan the QR code in the browser window to log into WhatsApp Web.")
            print("You have 60 seconds to scan the code.")
            print("===================\n")
            
            # Wait for the page to load completely
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.XPATH, '//div[@data-testid="chat-list"]'))
            )
            logger.info("Successfully logged into WhatsApp Web")
            
        except TimeoutException:
            logger.error("Timeout waiting for WhatsApp Web login")
            print("Failed to log into WhatsApp Web. Please try again.")
            return 0
        except Exception as e:
            logger.error(f"Error opening WhatsApp Web: {e}")
            return 0
        
        # Now start sending messages
        sent_count = 0
        
        # Sort leads by urgency (high urgency first)
        leads.sort(key=lambda x: 0 if x['urgency'] == 'HIGH' else 1 if x['urgency'] == 'MEDIUM' else 2)
        
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
        
        # Ensure WhatsApp Web is open and authenticated
        try:
            # First navigate to WhatsApp Web
            self.driver.get("https://web.whatsapp.com/")
            
            print("\n===== IMPORTANT =====")
            print("Please scan the QR code in the browser window to log into WhatsApp Web.")
            print("You have 60 seconds to scan the code.")
            print("===================\n")
            
            # Wait for the page to load completely
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.XPATH, '//div[@data-testid="chat-list"]'))
            )
            logger.info("Successfully logged into WhatsApp Web")
            
        except TimeoutException:
            logger.error("Timeout waiting for WhatsApp Web login")
            print("Failed to log into WhatsApp Web. Please try again.")
            return 0
        except Exception as e:
            logger.error(f"Error opening WhatsApp Web: {e}")
            return 0
        
        sent_count = 0
        
        for lead in urgent_leads:
            for agent_number in self.agent_numbers:
                success = self.send_lead_via_whatsapp(lead, agent_number)
                if success:
                    sent_count += 1
                    
        logger.info(f"Successfully sent {sent_count} urgent leads")
        return sent_count
    
    def send_test_message(self, phone_number):
        """Send a test WhatsApp message"""
        try:
            # Navigate to WhatsApp Web
            self.driver.get("https://web.whatsapp.com/")
            
            print("\n===== IMPORTANT =====")
            print("Please scan the QR code in the browser window to log into WhatsApp Web.")
            print("You have 60 seconds to scan the code.")
            print("===================\n")
            
            # Wait for WhatsApp Web to load
            WebDriverWait(self.driver, 60).until(
                EC.presence_of_element_located((By.XPATH, '//div[@data-testid="chat-list"]'))
            )
            
            # Send test message
            test_message = "This is a test message from your Property Lead Management System. If you received this, WhatsApp integration is working correctly!"
            
            success = self.send_whatsapp_message(phone_number, test_message)
            
            if success:
                logger.info(f"Test message sent successfully to {phone_number}")
                print(f"Test message sent successfully to {phone_number}")
            else:
                logger.error(f"Failed to send test message to {phone_number}")
                print(f"Failed to send test message to {phone_number}")
                
            return success
        except Exception as e:
            logger.error(f"Error sending test message: {e}")
            print(f"Error sending test message: {e}")
            return False
    
    def close(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()


if __name__ == "__main__":
    print("===== WhatsApp Lead Sender (Selenium) =====")
    
    sender = WhatsAppSeleniumSender()
    
    try:
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
            sender.send_test_message(phone)
            
        elif choice == '2':
            # Send unsent leads
            count = sender.distribute_leads_to_agents()
            print(f"Sent {count} leads via WhatsApp")
            
        elif choice == '3':
            # Send urgent leads
            count = sender.send_urgent_leads()
            print(f"Sent {count} urgent leads via WhatsApp")
            
        elif choice == '4':
            # Send all leads
            count = sender.distribute_leads_to_agents(send_all=True)
            print(f"Sent {count} leads via WhatsApp")
            
        else:
            print("Invalid choice. Please run the script again.")
    
    finally:
        # Make sure to close the browser
        sender.close()