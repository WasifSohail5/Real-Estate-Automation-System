import requests
import re
import time
import random
import logging
import os
from bs4 import BeautifulSoup
from database_operations import DatabaseManager

# Try to import selenium components
selenium_available = False
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    from webdriver_manager.chrome import ChromeDriverManager

    selenium_available = True
except ImportError:
    print("Selenium not available. Will use fallback methods for contact info.")

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('scraper.log'), logging.StreamHandler()]
)
logger = logging.getLogger('contact_scraper')


class ContactInfoScraper:
    """Enhanced scraper focusing on contact information extraction"""

    def __init__(self):
        self.db = DatabaseManager()
        self.session = requests.Session()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }
        self.session.headers.update(self.headers)

        # Initialize Selenium driver if available
        self.driver = None
        if selenium_available:
            self.setup_driver()

    def setup_driver(self, headless=True):
        """Set up Chrome WebDriver with optimized options"""
        if not selenium_available:
            return

        try:
            chrome_options = Options()
            if headless:
                chrome_options.add_argument("--headless=new")

            # Performance optimizations
            chrome_options.add_argument("--window-size=1280,1024")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-notifications")

            # Add user-agent
            chrome_options.add_argument(f"user-agent={self.headers['User-Agent']}")

            print("Setting up Chrome WebDriver...")
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(20)
            print("WebDriver setup complete.")
        except Exception as e:
            logger.error(f"Error setting up Chrome WebDriver: {e}")
            print(f"Failed to set up WebDriver: {e}")
            self.driver = None

    def close_driver(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()

    def _get_page(self, url, max_retries=3):
        """Get webpage content with retries using HTTP requests"""
        for attempt in range(max_retries):
            try:
                # Add small random delay
                time.sleep(random.uniform(1, 3))

                print(f"Attempt {attempt + 1} - Fetching URL: {url}")
                response = self.session.get(url, timeout=15)

                if response.status_code == 200:
                    print(f"Successfully loaded page ({len(response.text)} bytes)")
                    return response.text
                else:
                    print(f"Failed to load page: Status code {response.status_code}")
            except Exception as e:
                print(f"Error fetching URL (attempt {attempt + 1}): {str(e)}")

            # Wait before retry
            time.sleep(2)

        return None

    def _extract_urgency(self, text):
        """Extract urgency level from listing text"""
        if not text:
            return "NORMAL"

        text = text.lower()
        high_urgency_keywords = [
            "urgent", "urgently", "immediate", "quick sale", "quick deal",
            "fast sale", "hurry", "asap", "bargain", "distress", "must sell",
            "leaving city", "leaving country", "super hot", "investor rate"
        ]

        medium_urgency_keywords = [
            "good deal", "great deal", "negotiable", "price reduced",
            "below market", "motivated", "open to offers", "hot", "prime location"
        ]

        if any(keyword in text for keyword in high_urgency_keywords):
            return "HIGH"
        elif any(keyword in text for keyword in medium_urgency_keywords):
            return "MEDIUM"
        else:
            return "NORMAL"

    def _extract_size_from_text(self, text):
        """Extract property size from text"""
        if not text:
            return "N/A"

        size_patterns = [
            r"(\d+(?:\.\d+)?)\s*marla",
            r"(\d+(?:\.\d+)?)\s*kanal",
            r"(\d+(?:\.\d+)?)\s*sq(?:uare)?\s*(?:ft|feet|foot|yd|yard|meter|m)",
            r"(\d+(?:\.\d+)?)\s*(?:ft|feet)?\s*[×xX]\s*(\d+(?:\.\d+)?)\s*(?:ft|feet)?"
        ]

        for pattern in size_patterns:
            match = re.search(pattern, text.lower())
            if match:
                return match.group(0).strip()

        return "N/A"

    def _extract_phone_numbers(self, text):
        """Extract phone numbers from text using Pakistani mobile number patterns"""
        if not text:
            return []

        # Common Pakistani mobile number formats
        phone_patterns = [
            r'03\d{2}[-\s]?\d{7}',  # 0300-1234567
            r'\+92\s?3\d{2}[-\s]?\d{7}',  # +92 300 1234567
            r'92\s?3\d{2}[-\s]?\d{7}',  # 92 300 1234567
            r'03\d{2}\s?\d{3}\s?\d{4}',  # 0300 123 4567
            r'\d{4}\s?\d{7}',  # 0300 1234567 without prefix
            r'\d{4}\s?\d{3}\s?\d{4}'  # 0300 123 4567 without prefix
        ]

        all_phones = []
        for pattern in phone_patterns:
            matches = re.findall(pattern, text)
            all_phones.extend(matches)

        # Clean and standardize the numbers
        cleaned_phones = []
        for phone in all_phones:
            # Remove spaces, dashes, etc.
            clean = re.sub(r'[^\d+]', '', phone)

            # Standardize to international format if possible
            if clean.startswith('03'):
                clean = '+92' + clean[1:]
            elif clean.startswith('3'):
                clean = '+92' + clean

            if clean not in cleaned_phones:
                cleaned_phones.append(clean)

        return cleaned_phones

    def _extract_emails(self, text):
        """Extract email addresses from text"""
        if not text:
            return []

        # Email pattern
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'

        matches = re.findall(email_pattern, text)
        return list(set(matches))  # Remove duplicates

    def _get_contact_with_selenium(self, url, site_type='olx'):
        """Extract contact info using Selenium browser automation"""
        if not selenium_available or not self.driver:
            return None

        contact_info = {
            'phones': [],
            'emails': [],
            'has_contact_button': False,
            'button_text': None
        }

        try:
            print(f"Using Selenium to extract contact info from: {url}")

            # Load the page
            try:
                self.driver.get(url)
                time.sleep(3)  # Wait for page to load
            except Exception as e:
                print(f"Error loading page with Selenium: {e}")
                return contact_info

            # Extract page text for email and phone scanning
            page_text = self.driver.page_source
            contact_info['phones'] = self._extract_phone_numbers(page_text)
            contact_info['emails'] = self._extract_emails(page_text)

            # Find and click on contact buttons
            try:
                if site_type == 'olx':
                    # Different button types for OLX
                    button_selectors = [
                        '//button[contains(text(), "Show Phone Number")]',
                        '//button[contains(text(), "Chat")]',
                        '//button[contains(@class, "rui-3a8e1")]',
                        '//button[contains(@data-testid, "show-number")]',
                        '//span[contains(text(), "Show Phone Number")]',
                        '//button[contains(text(), "Contact Seller")]'
                    ]

                    # Try each selector
                    for selector in button_selectors:
                        try:
                            buttons = self.driver.find_elements(By.XPATH, selector)
                            if buttons:
                                contact_info['has_contact_button'] = True
                                contact_info['button_text'] = buttons[0].text
                                buttons[0].click()
                                time.sleep(2)  # Wait for number to appear

                                # Get the updated page content after click
                                updated_text = self.driver.page_source
                                new_phones = self._extract_phone_numbers(updated_text)

                                # Add any new phone numbers found
                                for phone in new_phones:
                                    if phone not in contact_info['phones']:
                                        contact_info['phones'].append(phone)

                                break
                        except Exception as e:
                            print(f"Error with button selector {selector}: {e}")
                            continue

                elif site_type == 'zameen':
                    # Different button types for Zameen.com
                    button_selectors = [
                        '//a[contains(text(), "Call")]',
                        '//button[contains(text(), "Call")]',
                        '//button[contains(@class, "c5ee3498")]',
                        '//a[contains(@href, "tel:")]',
                        '//button[contains(text(), "Contact Agent")]',
                        '//button[contains(text(), "Contact")]'
                    ]

                    # Try each selector
                    for selector in button_selectors:
                        try:
                            buttons = self.driver.find_elements(By.XPATH, selector)
                            if buttons:
                                contact_info['has_contact_button'] = True
                                contact_info['button_text'] = buttons[0].text

                                # Check if it's a direct tel: link
                                if selector == '//a[contains(@href, "tel:")]':
                                    href = buttons[0].get_attribute('href')
                                    if href and 'tel:' in href:
                                        phone = href.replace('tel:', '')
                                        if phone not in contact_info['phones']:
                                            contact_info['phones'].append(phone)
                                else:
                                    # Click and look for revealed numbers
                                    buttons[0].click()
                                    time.sleep(2)

                                    # Get updated page content
                                    updated_text = self.driver.page_source
                                    new_phones = self._extract_phone_numbers(updated_text)

                                    # Add any new phone numbers
                                    for phone in new_phones:
                                        if phone not in contact_info['phones']:
                                            contact_info['phones'].append(phone)

                                break
                        except Exception as e:
                            print(f"Error with button selector {selector}: {e}")
                            continue

                # Look for WhatsApp buttons/links
                whatsapp_selectors = [
                    '//a[contains(@href, "whatsapp")]',
                    '//button[contains(text(), "WhatsApp")]',
                    '//div[contains(text(), "WhatsApp")]'
                ]

                for selector in whatsapp_selectors:
                    try:
                        elements = self.driver.find_elements(By.XPATH, selector)
                        if elements:
                            href = elements[0].get_attribute('href')
                            if href and 'whatsapp' in href:
                                # Extract phone number from WhatsApp link
                                wa_match = re.search(r'(?:phone|text)=(\+?\d+)', href)
                                if wa_match:
                                    phone = wa_match.group(1)
                                    if phone not in contact_info['phones']:
                                        contact_info['phones'].append(phone)
                    except Exception:
                        continue

            except Exception as e:
                print(f"Error clicking contact button: {e}")

            # Take a screenshot for debugging (optional)
            screenshots_dir = "contact_screenshots"
            if not os.path.exists(screenshots_dir):
                os.makedirs(screenshots_dir)

            try:
                filename = url.split('/')[-1]
                if '?' in filename:
                    filename = filename.split('?')[0]
                filename = f"{screenshots_dir}/{filename}.png"
                self.driver.save_screenshot(filename)
                print(f"Saved screenshot to {filename}")
            except Exception as e:
                print(f"Error saving screenshot: {e}")

            # Look for any phone numbers displayed in specific elements
            phone_element_selectors = [
                '//span[contains(@class, "_3a--p")]',
                '//div[contains(text(), "+92")]',
                '//div[contains(text(), "03")]',
                '//span[contains(text(), "+92")]',
                '//span[contains(text(), "03")]'
            ]

            for selector in phone_element_selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for elem in elements:
                        text = elem.text.strip()
                        if text:
                            phones = self._extract_phone_numbers(text)
                            for phone in phones:
                                if phone not in contact_info['phones']:
                                    contact_info['phones'].append(phone)
                except Exception:
                    continue

            return contact_info

        except Exception as e:
            print(f"Error extracting contact info with Selenium: {e}")
            return contact_info

    def _get_contact_info(self, url, listing_html=None, site_type='olx'):
        """Extract contact information using multiple methods"""
        contact_info = {
            'phones': [],
            'emails': [],
            'seller_name': 'N/A'
        }

        # First try with Selenium if available
        if selenium_available and self.driver:
            selenium_info = self._get_contact_with_selenium(url, site_type)
            if selenium_info:
                contact_info['phones'] = selenium_info['phones']
                contact_info['emails'] = selenium_info['emails']

        # If we don't have HTML content yet, get it
        if not listing_html:
            listing_html = self._get_page(url)

        if not listing_html:
            return contact_info

        # Extract phones and emails from HTML
        phones = self._extract_phone_numbers(listing_html)
        for phone in phones:
            if phone not in contact_info['phones']:
                contact_info['phones'].append(phone)

        emails = self._extract_emails(listing_html)
        for email in emails:
            if email not in contact_info['emails']:
                contact_info['emails'].append(email)

        # Try to extract seller name
        if site_type == 'olx':
            seller_patterns = [
                r'<div[^>]*>Posted by</div>\s*<div[^>]*>([^<]+)</div>',
                r'<span[^>]*>Posted by</span>\s*<span[^>]*>([^<]+)</span>',
                r'<span[^>]*>Seller:\s*([^<]+)</span>'
            ]

            for pattern in seller_patterns:
                match = re.search(pattern, listing_html)
                if match:
                    contact_info['seller_name'] = match.group(1).strip()
                    break

        elif site_type == 'zameen':
            seller_patterns = [
                r'<div[^>]*>Agent</div>\s*<div[^>]*>([^<]+)</div>',
                r'<span[^>]*>Agent Name:\s*([^<]+)</span>',
                r'<div[^>]*class="[^"]*_5a89a970[^"]*"[^>]*>([^<]+)</div>'
            ]

            for pattern in seller_patterns:
                match = re.search(pattern, listing_html)
                if match:
                    contact_info['seller_name'] = match.group(1).strip()
                    break

        # Format contact information for display
        contact_text = "Contact through website"
        if contact_info['phones']:
            contact_text = ", ".join(contact_info['phones'])

        email_text = "N/A"
        if contact_info['emails']:
            email_text = ", ".join(contact_info['emails'])

        contact_info['contact_text'] = contact_text
        contact_info['email_text'] = email_text

        return contact_info

    def scrape_olx(self, url):
        """Scrape property listings from OLX with enhanced contact info"""
        all_listings = []
        html_content = self._get_page(url)

        if not html_content:
            return []

        print("Processing OLX page content...")

        # Extract listings with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Try multiple different approaches to find listings
        listing_elements = []

        # Approach 1: Look for listing cards
        print("Looking for OLX listing cards...")
        cards = soup.select('li[data-cy="l-card"], div.EIR5N, li._2qF0d')
        if cards:
            listing_elements = cards
            print(f"Found {len(cards)} OLX listing cards")

        # Approach 2: Look for elements with titles and prices
        if not listing_elements:
            print("Looking for title elements...")
            title_elements = soup.select('h2, span.fTZT3, span._2Vp0i')
            for elem in title_elements:
                parent = elem
                for _ in range(5):
                    if not parent:
                        break
                    parent = parent.parent
                    if parent and ('Rs' in parent.text or 'PKR' in parent.text):
                        listing_elements.append(parent)
                        break

            print(f"Found {len(listing_elements)} potential OLX listings using title elements")

        # If we still don't have listings, try regex on the raw HTML
        if not listing_elements:
            print("Using regex to find OLX listings...")
            property_pattern = r'<(li|div)[^>]*>.*?<h2[^>]*>.*?</h2>.*?(?:Rs|PKR).*?</(li|div)>'
            property_blocks = re.findall(property_pattern, html_content, re.DOTALL | re.IGNORECASE)

            if property_blocks:
                print(f"Found {len(property_blocks)} potential OLX listings using regex")

                for block_match in property_blocks:
                    block = block_match[0]

                    try:
                        title_match = re.search(r'<h2[^>]*>([^<]+)</h2>', block)
                        if not title_match:
                            continue

                        title = title_match.group(1).strip()

                        price_match = re.search(r'(?:Rs|PKR)[^\d]*(\d[\d,]*)', block)
                        price = f"Rs {price_match.group(1)}" if price_match else "N/A"

                        url_match = re.search(r'href="([^"]+)"', block)
                        listing_url = url_match.group(1) if url_match else ""
                        if listing_url and not listing_url.startswith('http'):
                            listing_url = f"https://www.olx.com.pk{listing_url}"

                        size = self._extract_size_from_text(title)

                        # Get contact info
                        contact_info = {
                            'phones': [],
                            'emails': [],
                            'seller_name': 'N/A',
                            'contact_text': 'Contact through OLX',
                            'email_text': 'N/A'
                        }

                        # Create property data
                        property_data = {
                            'title': title,
                            'price': price,
                            'location': 'Islamabad',
                            'description': f"{title}. Located in Islamabad.",
                            'listing_url': listing_url,
                            'source': 'OLX',
                            'urgency': self._extract_urgency(title),
                            'property_type': 'Plot',
                            'size': size,
                            'seller_name': contact_info['seller_name'],
                            'contact_number': contact_info['contact_text'],
                            'contact_info': contact_info
                        }

                        all_listings.append(property_data)
                        print(f"Extracted OLX listing: {title}")
                    except Exception as e:
                        print(f"Error extracting OLX listing: {str(e)}")

        # Process found elements with BeautifulSoup
        for element in listing_elements:
            try:
                title_elem = element.select_one('h2, span.fTZT3, span._2Vp0i')
                if not title_elem:
                    continue

                title = title_elem.text.strip()

                price = "N/A"
                price_elems = element.select('span')
                for elem in price_elems:
                    if 'Rs' in elem.text or 'PKR' in elem.text:
                        price = elem.text.strip()
                        break

                link_elem = element.select_one('a[href]')
                listing_url = link_elem['href'] if link_elem else ""
                if listing_url and not listing_url.startswith('http'):
                    listing_url = f"https://www.olx.com.pk{listing_url}"

                size = self._extract_size_from_text(title)

                # Get contact info if we have a valid URL
                contact_info = {
                    'phones': [],
                    'emails': [],
                    'seller_name': 'N/A',
                    'contact_text': 'Contact through OLX',
                    'email_text': 'N/A'
                }

                # Create property data
                property_data = {
                    'title': title,
                    'price': price,
                    'location': 'Islamabad',
                    'description': f"{title}. Located in Islamabad.",
                    'listing_url': listing_url,
                    'source': 'OLX',
                    'urgency': self._extract_urgency(title),
                    'property_type': 'Plot',
                    'size': size,
                    'seller_name': contact_info['seller_name'],
                    'contact_number': contact_info['contact_text'],
                    'contact_info': contact_info
                }

                all_listings.append(property_data)
                print(f"Extracted OLX listing: {title}")
            except Exception as e:
                print(f"Error processing OLX element: {str(e)}")

        # Now get detailed contact information for each listing
        listings_with_contact = []

        # Process only 10 listings to avoid timeouts
        process_count = min(10, len(all_listings))
        print(f"Extracting contact information for {process_count} OLX listings...")

        for i, listing in enumerate(all_listings[:process_count]):
            if listing['listing_url']:
                print(f"Getting contact info for listing {i + 1}/{process_count}: {listing['title']}")
                contact_info = self._get_contact_info(listing['listing_url'], site_type='olx')

                # Update the listing with contact information
                listing['seller_name'] = contact_info['seller_name'] if contact_info['seller_name'] != 'N/A' else \
                listing['seller_name']
                listing['contact_number'] = contact_info['contact_text']
                listing['contact_info'] = contact_info

                print(f"Contact info: {contact_info['contact_text']}")

            listings_with_contact.append(listing)

            # Add some delay between requests
            if i < process_count - 1:
                time.sleep(random.uniform(1, 2))

        # Add remaining listings without fetching contact info
        if len(all_listings) > process_count:
            listings_with_contact.extend(all_listings[process_count:])

        print(f"Successfully extracted {len(listings_with_contact)} listings from OLX")
        return listings_with_contact

    def scrape_zameen(self, url):
        """Scrape property listings from Zameen.com with enhanced contact info"""
        all_listings = []
        html_content = self._get_page(url)

        if not html_content:
            return []

        print("Processing Zameen.com page content...")

        # Extract listing URLs first to handle dynamically loaded content better
        listing_urls = []
        url_matches = re.findall(r'href="(/Property/[^"]+\.html)"', html_content)
        for url_match in url_matches:
            if url_match not in listing_urls:
                listing_urls.append(url_match)

        print(f"Found {len(listing_urls)} Zameen.com listing URLs")

        # Process only a subset to avoid timeouts
        process_count = min(10, len(listing_urls))
        print(f"Processing {process_count} Zameen.com listings for contact information...")

        # Process each listing URL to get details
        for i, listing_url in enumerate(listing_urls[:process_count]):
            try:
                full_url = f"https://www.zameen.com{listing_url}"

                print(f"Processing listing {i + 1}/{process_count}: {full_url}")

                # Get the listing page
                listing_html = self._get_page(full_url)
                if not listing_html:
                    continue

                # Parse the HTML
                listing_soup = BeautifulSoup(listing_html, 'html.parser')

                # Extract title
                title = "Property in Islamabad"
                title_elem = listing_soup.select_one('h1')
                if title_elem:
                    title = title_elem.text.strip()

                # Extract price
                price = "N/A"
                price_matches = re.findall(r'PKR\s*[\d,.]+|Rs\.?\s*[\d,.]+|[\d,.]+\s*(?:lac|lakh|crore)', listing_html)
                if price_matches:
                    price = price_matches[0].strip()

                # Extract location
                location = "Islamabad"
                location_elem = listing_soup.select_one('div._1a682f13, div.b1f5314c')
                if location_elem:
                    location = location_elem.text.strip()

                # Extract description
                description = f"{title}. Located in {location}."
                desc_elem = listing_soup.select_one('div._96aa05ec, div.f063b7bf')
                if desc_elem:
                    description = desc_elem.text.strip()

                # Extract size
                size = "N/A"
                spec_elems = listing_soup.select('li._17984a2c, div.fe2e5c5d')
                for elem in spec_elems:
                    text = elem.text.lower()
                    if 'area' in text or 'marla' in text or 'kanal' in text:
                        size = elem.text.strip()
                        break

                if size == "N/A":
                    size = self._extract_size_from_text(f"{title} {description}")

                # Get contact information
                contact_info = self._get_contact_info(full_url, listing_html, site_type='zameen')

                # Check if it's a hot/featured listing
                is_hot = False
                hot_elems = listing_soup.select('.SUPER.HOT, .ae84a87a, .aeea0330')
                is_hot = len(hot_elems) > 0

                # Create property data
                property_data = {
                    'title': title,
                    'price': price,
                    'location': location,
                    'description': description,
                    'listing_url': full_url,
                    'source': 'Zameen.com',
                    'urgency': "HIGH" if is_hot else self._extract_urgency(f"{title} {description}"),
                    'property_type': 'Plot',
                    'size': size,
                    'seller_name': contact_info['seller_name'],
                    'contact_number': contact_info['contact_text'],
                    'contact_info': contact_info
                }

                all_listings.append(property_data)
                print(f"Extracted Zameen.com listing: {title}")
                print(f"Contact: {contact_info['contact_text']}")

                # Add a small delay to avoid overloading the server
                if i < process_count - 1:
                    time.sleep(random.uniform(1, 2))

            except Exception as e:
                print(f"Error processing Zameen.com listing: {str(e)}")

        # Process remaining listings using the main page
        if len(listing_urls) > process_count:
            print(f"Processing remaining listings from Zameen.com main page...")

            # Parse the HTML
            soup = BeautifulSoup(html_content, 'html.parser')

            # Try to find property cards
            cards = soup.select('li[role="article"], article.listingCard, div._357a9937')
            print(f"Found {len(cards)} Zameen.com listing cards")

            for i, card in enumerate(cards):
                try:
                    # Skip if we already processed this listing
                    link_elem = card.select_one('a[href]')
                    if not link_elem or not link_elem.has_attr('href'):
                        continue

                    listing_path = link_elem['href']
                    if listing_path in listing_urls[:process_count]:
                        continue

                    # Extract title
                    title_elem = card.select_one('h2.c21a3f5e, h2')
                    if not title_elem:
                        continue

                    title = title_elem.text.strip()

                    # Extract price
                    price = "N/A"
                    price_elem = card.select_one('span.f343d9ce, span.c4fc20ba, span.d6e81fd0')
                    if price_elem:
                        price = price_elem.text.strip()

                    # Extract URL
                    listing_url = link_elem['href']
                    if listing_url and not listing_url.startswith('http'):
                        listing_url = f"https://www.zameen.com{listing_url}"

                    # Extract size
                    size = "N/A"
                    size_elem = card.select_one('span.b1a784e2')
                    if size_elem:
                        size = size_elem.text.strip()
                    else:
                        # Try to extract from title
                        size = self._extract_size_from_text(title)

                    # Create basic contact info since we're not visiting the detail page
                    contact_info = {
                        'phones': [],
                        'emails': [],
                        'seller_name': 'N/A',
                        'contact_text': 'Contact through Zameen.com',
                        'email_text': 'N/A'
                    }

                    # Create property data
                    property_data = {
                        'title': title,
                        'price': price,
                        'location': 'Islamabad',
                        'description': f"{title}. Located in Islamabad.",
                        'listing_url': listing_url,
                        'source': 'Zameen.com',
                        'urgency': self._extract_urgency(title),
                        'property_type': 'Plot',
                        'size': size,
                        'seller_name': contact_info['seller_name'],
                        'contact_number': contact_info['contact_text'],
                        'contact_info': contact_info
                    }

                    all_listings.append(property_data)
                    print(f"Extracted Zameen.com listing from main page: {title}")
                except Exception as e:
                    print(f"Error processing Zameen.com card: {str(e)}")

        print(f"Successfully extracted {len(all_listings)} listings from Zameen.com")
        return all_listings

    def save_listings_to_db(self, listings):
        """Save listings to database"""
        saved_count = 0

        for listing in listings:
            try:
                # Prepare data for database
                lead_data = {
                    'title': listing['title'],
                    'description': listing['description'],
                    'price': listing['price'],
                    'location': listing['location'],
                    'property_type': listing['property_type'],
                    'size': listing['size'],
                    'seller_name': listing['seller_name'],
                    'contact_number': listing['contact_number'],
                    'listing_url': listing['listing_url'],
                    'source': listing['source'],
                    'urgency': listing['urgency']
                }

                # Add additional contact info as JSON in description if available
                if 'contact_info' in listing and (
                        listing['contact_info']['phones'] or listing['contact_info']['emails']):
                    contact_note = "\n\nContact Information:\n"
                    if listing['contact_info']['phones']:
                        contact_note += f"Phones: {', '.join(listing['contact_info']['phones'])}\n"
                    if listing['contact_info']['emails']:
                        contact_note += f"Emails: {', '.join(listing['contact_info']['emails'])}\n"

                    lead_data['description'] = lead_data['description'] + contact_note

                lead_id = self.db.add_lead(lead_data)
                if lead_id:
                    saved_count += 1
                    logger.info(f"Saved listing to database with ID {lead_id}: {listing['title']}")
                    print(f"Saved: {listing['title']} - {listing['price']} - {listing['contact_number']}")
            except Exception as e:
                logger.error(f"Error saving listing to database: {str(e)}")
                print(f"Error adding lead: {str(e)}")

        return saved_count

    def run(self, olx_url, zameen_url):
        """Run the contact-focused scraper on specified URLs"""
        total_saved = 0

        try:
            # Scrape OLX
            print("\nStarting OLX scraper...")
            logger.info(f"Starting scraping of OLX URL: {olx_url}")
            olx_listings = self.scrape_olx(olx_url)
            logger.info(f"Found {len(olx_listings)} listings on OLX")

            print(f"Found {len(olx_listings)} OLX listings. Saving to database...")
            olx_saved = self.save_listings_to_db(olx_listings)
            logger.info(f"Saved {olx_saved} OLX listings to database")
            total_saved += olx_saved

            # Scrape Zameen
            print("\nStarting Zameen scraper...")
            logger.info(f"Starting scraping of Zameen URL: {zameen_url}")
            zameen_listings = self.scrape_zameen(zameen_url)
            logger.info(f"Found {len(zameen_listings)} listings on Zameen")

            print(f"Found {len(zameen_listings)} Zameen listings. Saving to database...")
            zameen_saved = self.save_listings_to_db(zameen_listings)
            logger.info(f"Saved {zameen_saved} Zameen listings to database")
            total_saved += zameen_saved

            # Get urgent leads
            urgent_leads = self.db.get_urgent_leads()
            logger.info(f"Found {len(urgent_leads)} urgent leads in database")

            # Process contact info in all listings
            listings_with_contact = []
            for listing in olx_listings + zameen_listings:
                if 'contact_info' in listing and (
                        listing['contact_info']['phones'] or listing['contact_info']['emails']):
                    listings_with_contact.append(listing)

            return {
                'olx_count': len(olx_listings),
                'zameen_count': len(zameen_listings),
                'total_saved': total_saved,
                'urgent_count': len(urgent_leads),
                'urgent_leads': urgent_leads,
                'contact_info_count': len(listings_with_contact),
                'listings_with_contact': listings_with_contact
            }

        finally:
            # Always close the driver to free resources
            if self.driver:
                self.close_driver()


if __name__ == "__main__":
    print("===== Property Contact Info Scraper =====")
    print("Scraping with enhanced contact information extraction...")

    # Direct URLs to scrape
    olx_url = "https://www.olx.com.pk/islamabad_g4060615/land-plots_c40"
    zameen_url = "https://www.zameen.com/Plots/Islamabad-3-1.html"

    # Create the contact info scraper
    scraper = ContactInfoScraper()

    results = scraper.run(olx_url, zameen_url)

    print("\n===== Scraping Results =====")
    print(f"OLX Listings found: {results['olx_count']}")
    print(f"Zameen Listings found: {results['zameen_count']}")
    print(f"Total listings saved to database: {results['total_saved']}")
    print(f"Listings with contact info: {results['contact_info_count']}")
    print(f"Urgent leads found: {results['urgent_count']}")

    # Display some listings with contact info
    if results['contact_info_count'] > 0:
        print("\n===== Listings With Contact Information =====")
        for i, listing in enumerate(results['listings_with_contact'][:5]):
            print(f"{i + 1}. {listing['title']}")
            print(f"   Price: {listing['price']}")
            print(f"   Location: {listing['location']}")
            print(f"   Contact: {listing['contact_number']}")
            if listing['contact_info']['emails']:
                print(f"   Email: {', '.join(listing['contact_info']['emails'])}")
            print()

    print("=============================")