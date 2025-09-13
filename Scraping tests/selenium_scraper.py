import time
import random
import re
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from database_operations import DatabaseManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('scraper.log'), logging.StreamHandler()]
)
logger = logging.getLogger('selenium_scraper')


class SeleniumScraper:
    """Enhanced scraper using Selenium for OLX and Zameen.com"""

    def __init__(self, headless=True):
        self.db = DatabaseManager()
        self.setup_driver(headless)

    def setup_driver(self, headless=True):
        """Set up Chrome WebDriver with appropriate options"""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")

        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--ignore-certificate-errors")

        # Add a user-agent to make the browser look more like a real user
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36")

        try:
            # Install and setup the WebDriver
            print("Setting up Chrome WebDriver...")
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.set_page_load_timeout(30)  # Set timeout to 30 seconds
            print("WebDriver setup complete.")
        except Exception as e:
            logger.error(f"Error setting up Chrome WebDriver: {e}")
            print(f"Failed to set up WebDriver: {e}")
            raise

    def close_driver(self):
        """Close the WebDriver"""
        if hasattr(self, 'driver'):
            self.driver.quit()

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

    def _random_sleep(self, min_sec=1, max_sec=3):
        """Sleep for a random duration to avoid detection"""
        time.sleep(random.uniform(min_sec, max_sec))

    def scrape_olx(self, url):
        """Scrape property listings from OLX using Selenium"""
        all_listings = []

        try:
            print(f"Navigating to OLX: {url}")
            self.driver.get(url)

            # Wait for page to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                # Additional wait for content to load
                self._random_sleep(2, 4)
                print("OLX page loaded successfully.")
            except TimeoutException:
                logger.warning("Timeout waiting for OLX page to load")
                print("Timeout waiting for OLX page to load.")
                return []

            # Find all listings
            print("Looking for OLX property listings...")

            # Try multiple different selectors that might contain listings
            listing_elements = []
            selectors = [
                "//li[contains(@data-cy, 'l-card')]",  # XPath for listing cards
                "//div[contains(@class, 'EIR5N')]",  # Class used in some OLX versions
                "//a[contains(@class, '_2KkSl')]",  # Links to listings
                "//div[contains(@class, 'ee2b0479')]",  # Another potential class
                "//li[@data-testid='listing-card']"  # Test ID for listings
            ]

            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        listing_elements = elements
                        print(f"Found {len(elements)} OLX listings using selector: {selector}")
                        break
                except Exception as e:
                    logger.error(f"Error finding elements with selector {selector}: {e}")

            if not listing_elements:
                # If we still don't have listings, try a more general approach
                print("Trying alternative selectors...")
                try:
                    # Look for any element that might be a card with a link
                    elements = self.driver.find_elements(By.XPATH,
                                                         "//a[.//h2] | //li[.//a[.//span[contains(text(), 'Rs')]]]")
                    if elements:
                        listing_elements = elements
                        print(f"Found {len(elements)} potential OLX listings using fallback selector")
                except Exception as e:
                    logger.error(f"Error with fallback selector: {e}")

            # Process each listing
            for i, element in enumerate(listing_elements):
                try:
                    print(f"Processing OLX listing {i + 1}/{len(listing_elements)}...")

                    # Extract title
                    title = "Property in Islamabad"
                    try:
                        title_elem = element.find_element(By.XPATH,
                                                          ".//h2 | .//span[contains(@class, '_2Vp0i')] | .//span[string-length(text()) > 15]")
                        title = title_elem.text.strip()
                    except Exception:
                        # Try to get any text that might be a title
                        try:
                            texts = element.find_elements(By.XPATH, ".//span | .//div")
                            for text_elem in texts:
                                text = text_elem.text.strip()
                                if len(text) > 15:  # Likely a title if it's this long
                                    title = text
                                    break
                        except Exception:
                            pass

                    # Extract price
                    price = "N/A"
                    try:
                        # Look for elements containing Rs or PKR
                        price_elems = element.find_elements(By.XPATH,
                                                            ".//span[contains(text(), 'Rs') or contains(text(), 'PKR')] | " +
                                                            ".//div[contains(text(), 'Rs') or contains(text(), 'PKR')]")
                        if price_elems:
                            price = price_elems[0].text.strip()
                    except Exception:
                        pass

                    # Extract location
                    location = "Islamabad"
                    try:
                        loc_elems = element.find_elements(By.XPATH,
                                                          ".//span[contains(@class, '_2TVI3') or contains(@class, '_3eEwF')] | " +
                                                          ".//span[text()[contains(., 'Islamabad')]]")
                        if loc_elems:
                            location = loc_elems[0].text.strip()
                    except Exception:
                        pass

                    # Get URL
                    listing_url = ""
                    try:
                        # If the element itself is a link
                        if element.tag_name == 'a':
                            listing_url = element.get_attribute('href')
                        else:
                            # Otherwise look for a link inside
                            link = element.find_element(By.XPATH, ".//a")
                            listing_url = link.get_attribute('href')
                    except Exception:
                        # If we can't get the URL, skip this listing
                        continue

                    # Extract size from title
                    size = self._extract_size_from_text(title)

                    # Check if it's featured
                    is_featured = False
                    try:
                        featured_elems = element.find_elements(By.XPATH,
                                                               ".//*[contains(text(), 'Featured') or contains(text(), 'SUPER')]")
                        is_featured = len(featured_elems) > 0
                    except Exception:
                        pass

                    # Create description
                    description = f"{title}. Located in {location}."
                    if size != "N/A":
                        description += f" {size} plot."

                    # Determine urgency
                    urgency = "HIGH" if is_featured else self._extract_urgency(title)

                    # Create property data
                    property_data = {
                        'title': title,
                        'price': price,
                        'location': location,
                        'description': description,
                        'listing_url': listing_url,
                        'source': 'OLX',
                        'urgency': urgency,
                        'property_type': 'Plot',
                        'size': size,
                        'seller_name': 'N/A',
                        'contact_number': 'Contact through OLX'
                    }

                    all_listings.append(property_data)
                    print(f"Found OLX listing: {title} - {price}")

                except Exception as e:
                    logger.error(f"Error processing OLX listing {i + 1}: {e}")
                    continue

            # If we have links to individual listings, visit each one for more details
            if len(all_listings) > 0:
                print("\nGetting detailed information from OLX listings...")
                detailed_listings = []

                # Process up to 10 listings in detail to avoid long runtime
                for i, listing in enumerate(all_listings[:10]):
                    try:
                        print(f"Getting details for listing {i + 1}/{min(10, len(all_listings))}: {listing['title']}")
                        detailed_data = self._get_olx_listing_details(listing['listing_url'], listing)
                        if detailed_data:
                            detailed_listings.append(detailed_data)
                        else:
                            detailed_listings.append(listing)  # Use the basic data if detailed scrape fails

                        # Wait between requests
                        self._random_sleep(2, 4)
                    except Exception as e:
                        logger.error(f"Error getting details for OLX listing {listing['title']}: {e}")
                        detailed_listings.append(listing)  # Use the basic data if detailed scrape fails

                # Add the remaining listings without detailed information
                if len(all_listings) > 10:
                    detailed_listings.extend(all_listings[10:])

                all_listings = detailed_listings

        except Exception as e:
            logger.error(f"Error scraping OLX: {e}")
            print(f"Error during OLX scraping: {e}")

        return all_listings

    def _get_olx_listing_details(self, url, basic_data):
        """Get detailed information from individual OLX listing page"""
        try:
            self.driver.get(url)

            # Wait for page to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "h1"))
                )
                # Additional wait
                self._random_sleep(1, 2)
            except TimeoutException:
                logger.warning(f"Timeout waiting for OLX listing page to load: {url}")
                return None

            # Extract enhanced title if available
            try:
                title_elem = self.driver.find_element(By.XPATH, "//h1")
                title = title_elem.text.strip()
                if title:
                    basic_data['title'] = title
            except NoSuchElementException:
                pass

            # Extract enhanced price if available
            try:
                price_elem = self.driver.find_element(By.XPATH,
                                                      "//span[contains(@class, '_2xKfz')] | " +
                                                      "//span[@data-aut-id='itemPrice'] | " +
                                                      "//span[contains(text(), 'Rs') and contains(@class, 'Text_Text__text__')]")
                price = price_elem.text.strip()
                if price:
                    basic_data['price'] = price
            except NoSuchElementException:
                pass

            # Extract detailed description if available
            try:
                desc_elem = self.driver.find_element(By.XPATH,
                                                     "//div[contains(@class, '_2EuAR')] | " +
                                                     "//div[@data-aut-id='itemDescriptionContent'] | " +
                                                     "//div[contains(@class, 'g5mtbi-Text')]")
                description = desc_elem.text.strip()
                if description:
                    basic_data['description'] = description
            except NoSuchElementException:
                pass

            # Extract seller info if available
            try:
                seller_elem = self.driver.find_element(By.XPATH,
                                                       "//div[contains(@class, '_3oOe9')] | " +
                                                       "//span[@data-aut-id='contactName']")
                seller_name = seller_elem.text.strip()
                if seller_name:
                    basic_data['seller_name'] = seller_name
            except NoSuchElementException:
                pass

            # Extract contact info if available
            try:
                # Try to click the show number button if present
                try:
                    show_number_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH,
                                                    "//button[contains(text(), 'Show Phone Number')] | " +
                                                    "//button[contains(text(), 'Click to show phone number')] | " +
                                                    "//button[contains(@class, 'rui-3a8e1')]"))
                    )
                    show_number_button.click()
                    self._random_sleep(1, 2)

                    # Get the phone number after clicking
                    phone_elem = self.driver.find_element(By.XPATH,
                                                          "//span[contains(@class, '_3a--p')] | " +
                                                          "//div[contains(text(), '+92')] | " +
                                                          "//div[contains(text(), '03')]")
                    phone = phone_elem.text.strip()
                    if phone:
                        basic_data['contact_number'] = phone
                except (TimeoutException, NoSuchElementException):
                    pass
            except Exception:
                pass

            # Extract property details (size, etc.) if available
            try:
                detail_rows = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'rui-2CYS')]")
                for row in detail_rows:
                    try:
                        label = row.find_element(By.XPATH, ".//span[1]").text.strip().lower()
                        value = row.find_element(By.XPATH, ".//span[2]").text.strip()

                        if 'area' in label or 'size' in label:
                            basic_data['size'] = value
                        elif 'type' in label:
                            basic_data['property_type'] = value
                    except Exception:
                        continue
            except Exception:
                pass

            # If size wasn't found in details, try to extract from title or description
            if basic_data['size'] == "N/A":
                size = self._extract_size_from_text(f"{basic_data['title']} {basic_data['description']}")
                if size != "N/A":
                    basic_data['size'] = size

            return basic_data

        except Exception as e:
            logger.error(f"Error getting OLX listing details: {e}")
            return None

    def scrape_zameen(self, url):
        """Scrape property listings from Zameen.com using Selenium"""
        all_listings = []

        try:
            print(f"Navigating to Zameen.com: {url}")
            self.driver.get(url)

            # Wait for page to load
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                # Additional wait for content to load
                self._random_sleep(3, 5)
                print("Zameen.com page loaded successfully.")
            except TimeoutException:
                logger.warning("Timeout waiting for Zameen.com page to load")
                print("Timeout waiting for Zameen.com page to load.")
                return []

            # Find all listings
            print("Looking for Zameen.com property listings...")

            # Try multiple different selectors that might contain listings
            listing_elements = []
            selectors = [
                "//li[@role='article']",  # Most common for Zameen.com
                "//article[contains(@class, 'listingCard')]",  # Another common pattern
                "//div[contains(@class, '_357a9937')]",  # Class used in some versions
            ]

            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    if elements:
                        listing_elements = elements
                        print(f"Found {len(elements)} Zameen.com listings using selector: {selector}")
                        break
                except Exception as e:
                    logger.error(f"Error finding elements with selector {selector}: {e}")

            if not listing_elements:
                print("No listings found on Zameen.com. Trying alternative approach...")
                try:
                    # Look for elements with prices as a fallback
                    price_elements = self.driver.find_elements(By.XPATH,
                                                               "//span[contains(@class, 'f343d9ce')] | //span[contains(@class, 'c4fc20ba')]")
                    if price_elements:
                        # Navigate up to find potential listing containers
                        listing_elements = []
                        for price_elem in price_elements:
                            try:
                                # Go up a few levels to find the container
                                container = price_elem
                                for _ in range(4):  # Go up to 4 levels
                                    parent = container.find_element(By.XPATH, "./..")
                                    if parent.tag_name in ['li', 'article', 'div']:
                                        container = parent
                                    else:
                                        break

                                if container not in listing_elements:
                                    listing_elements.append(container)
                            except Exception:
                                continue

                        print(f"Found {len(listing_elements)} potential Zameen.com listings using price elements")
                except Exception as e:
                    logger.error(f"Error with fallback listing detection: {e}")

            # Process each listing
            for i, element in enumerate(listing_elements):
                try:
                    print(f"Processing Zameen.com listing {i + 1}/{len(listing_elements)}...")

                    # Extract listing URL first
                    listing_url = ""
                    try:
                        link_elem = element.find_element(By.XPATH, ".//a")
                        listing_url = link_elem.get_attribute('href')
                        if not listing_url.startswith('http'):
                            listing_url = f"https://www.zameen.com{listing_url}"
                    except NoSuchElementException:
                        # If we can't find a link, try to get one from the element itself
                        if element.tag_name == 'a':
                            listing_url = element.get_attribute('href')

                    if not listing_url:
                        continue  # Skip if no URL

                    # Use the URL to get detailed info directly
                    detailed_data = self._get_zameen_listing_details(listing_url)
                    if detailed_data:
                        all_listings.append(detailed_data)
                        continue

                    # If detailed info fails, try to extract from the card
                    title = "Property in Islamabad"
                    try:
                        title_elem = element.find_element(By.XPATH, ".//h2[contains(@class, 'c21a3f5e')] | .//h2")
                        title = title_elem.text.strip()
                    except NoSuchElementException:
                        # Try to find any text that might be a title
                        text_elements = element.find_elements(By.XPATH, ".//div[string-length(text()) > 15]")
                        for text_elem in text_elements:
                            if len(text_elem.text.strip()) > 15:
                                title = text_elem.text.strip()
                                break

                    # Extract price
                    price = "N/A"
                    try:
                        price_elem = element.find_element(By.XPATH,
                                                          ".//span[contains(@class, 'f343d9ce')] | " +
                                                          ".//span[contains(@class, 'c4fc20ba')] | " +
                                                          ".//span[contains(@class, 'd6e81fd0')]")
                        price = price_elem.text.strip()
                    except NoSuchElementException:
                        pass

                    # Extract location
                    location = "Islamabad"
                    try:
                        loc_elem = element.find_element(By.XPATH,
                                                        ".//div[contains(@class, '_162e6469')] | " +
                                                        ".//div[contains(@class, 'c03f0d38')]")
                        location = loc_elem.text.strip()
                    except NoSuchElementException:
                        pass

                    # Extract size
                    size = "N/A"
                    try:
                        size_elem = element.find_element(By.XPATH,
                                                         ".//span[contains(@class, 'b1a784e2')] | " +
                                                         ".//span[contains(text(), 'Marla')] | " +
                                                         ".//span[contains(text(), 'Kanal')]")
                        size = size_elem.text.strip()
                    except NoSuchElementException:
                        # Try to extract from title
                        size = self._extract_size_from_text(title)

                    # Check if it's a featured/hot listing
                    is_featured = False
                    try:
                        featured_elem = element.find_element(By.XPATH,
                                                             ".//*[contains(text(), 'SUPER HOT') or contains(@class, 'ae84a87a')]")
                        is_featured = True
                    except NoSuchElementException:
                        pass

                    # Create property data
                    property_data = {
                        'title': title,
                        'price': price,
                        'location': location,
                        'description': f"{title}. Located in {location}.",
                        'listing_url': listing_url,
                        'source': 'Zameen.com',
                        'urgency': "HIGH" if is_featured else self._extract_urgency(title),
                        'property_type': 'Plot',
                        'size': size,
                        'seller_name': 'N/A',
                        'contact_number': 'Contact through Zameen.com'
                    }

                    all_listings.append(property_data)
                    print(f"Found Zameen.com listing: {title} - {price}")

                except Exception as e:
                    logger.error(f"Error processing Zameen.com listing {i + 1}: {e}")
                    continue

            # If we didn't get enough listings from the cards, try to find links and visit each page
            if len(all_listings) < 5:
                print("Looking for more Zameen.com listings from links...")
                try:
                    # Find all property links
                    property_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/Property/')]")
                    property_urls = []

                    # Get unique URLs
                    for link in property_links:
                        url = link.get_attribute('href')
                        if url and url not in property_urls:
                            property_urls.append(url)

                    print(f"Found {len(property_urls)} additional property links")

                    # Visit each link (up to 10)
                    for i, url in enumerate(property_urls[:10]):
                        try:
                            print(f"Getting details for property {i + 1}/{min(10, len(property_urls))}")
                            detailed_data = self._get_zameen_listing_details(url)
                            if detailed_data:
                                all_listings.append(detailed_data)

                            # Wait between requests
                            self._random_sleep(2, 4)
                        except Exception as e:
                            logger.error(f"Error getting details for Zameen.com property: {e}")
                            continue
                except Exception as e:
                    logger.error(f"Error finding additional Zameen.com properties: {e}")

        except Exception as e:
            logger.error(f"Error scraping Zameen.com: {e}")
            print(f"Error during Zameen.com scraping: {e}")

        return all_listings

    def _get_zameen_listing_details(self, url):
        """Get detailed information from individual Zameen.com listing page"""
        try:
            self.driver.get(url)

            # Wait for page to load
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "h1"))
                )
                # Additional wait
                self._random_sleep(1, 3)
            except TimeoutException:
                logger.warning(f"Timeout waiting for Zameen.com listing page to load: {url}")
                return None

            # Extract title
            title = "Property in Islamabad"
            try:
                title_elem = self.driver.find_element(By.XPATH,
                                                      "//h1[contains(@class, 'fcae1c42')] | //h1[contains(@class, 'ef2636f4')] | //h1")
                title = title_elem.text.strip()
            except NoSuchElementException:
                pass

            # Extract price
            price = "N/A"
            try:
                price_elem = self.driver.find_element(By.XPATH,
                                                      "//span[contains(@class, 'c4fc20ba')] | " +
                                                      "//div[contains(@class, 'd8c979d0')] | " +
                                                      "//span[contains(text(), 'PKR')]")
                price = price_elem.text.strip()
            except NoSuchElementException:
                pass

            # Extract location
            location = "Islamabad"
            try:
                location_elem = self.driver.find_element(By.XPATH,
                                                         "//div[contains(@class, '_1a682f13')] | " +
                                                         "//div[contains(@class, 'b1f5314c')]")
                location = location_elem.text.strip()
            except NoSuchElementException:
                pass

            # Extract description
            description = f"{title}. Located in {location}."
            try:
                desc_elem = self.driver.find_element(By.XPATH,
                                                     "//div[contains(@class, '_96aa05ec')] | " +
                                                     "//div[contains(@class, 'f063b7bf')] | " +
                                                     "//div[contains(@class, 'b58e2e99')]")
                description = desc_elem.text.strip()
            except NoSuchElementException:
                pass

            # Extract property details
            property_type = "Plot"
            size = "N/A"
            seller_name = "N/A"
            contact_number = "Contact through Zameen.com"

            # Try to find property specs
            try:
                detail_rows = self.driver.find_elements(By.XPATH,
                                                        "//li[contains(@class, '_17984a2c')] | " +
                                                        "//div[contains(@class, 'fe2e5c5d')] | " +
                                                        "//li[contains(@class, 'e0c6cb40')]")

                for row in detail_rows:
                    row_text = row.text.strip().lower()

                    # Extract size information
                    if 'area' in row_text or 'size' in row_text:
                        size_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:marla|kanal|sq)', row_text)
                        if size_match:
                            size = size_match.group(0)

                    # Extract property type
                    if 'type' in row_text:
                        if 'residential' in row_text:
                            property_type = "Residential Plot"
                        elif 'commercial' in row_text:
                            property_type = "Commercial Plot"
            except Exception:
                pass

            # If size not found in details, try to extract from title or description
            if size == "N/A":
                size = self._extract_size_from_text(f"{title} {description}")

            # Try to get seller information
            try:
                seller_elem = self.driver.find_element(By.XPATH,
                                                       "//div[contains(@class, '_5a89a970')] | " +
                                                       "//div[contains(@class, 'b1441c3e')] | " +
                                                       "//div[contains(@class, 'e5c5a3e4')]")
                seller_name = seller_elem.text.strip()
            except NoSuchElementException:
                pass

            # Try to get contact information
            try:
                # Check if there's a "Call" button
                call_buttons = self.driver.find_elements(By.XPATH,
                                                         "//button[contains(@class, 'c5ee3498')] | " +
                                                         "//button[contains(text(), 'Call')] | " +
                                                         "//a[contains(@href, 'tel:')]")

                if call_buttons:
                    # Try to extract phone from button or element
                    for btn in call_buttons:
                        try:
                            # Try direct text first
                            if '03' in btn.text or '+92' in btn.text:
                                contact_number = btn.text.strip()
                                break

                            # Try href attribute for tel: links
                            href = btn.get_attribute('href')
                            if href and 'tel:' in href:
                                contact_number = href.replace('tel:', '')
                                break

                            # If possible, try clicking the button to reveal number
                            # Only attempt this if it doesn't navigate away (e.g., it's not a direct tel: link)
                            if not href or 'tel:' not in href:
                                # Store current URL to check if we navigate away
                                current_url = self.driver.current_url
                                btn.click()
                                self._random_sleep(1, 2)

                                # If we're still on the same page, look for newly revealed numbers
                                if self.driver.current_url == current_url:
                                    phone_elems = self.driver.find_elements(By.XPATH,
                                                                            "//span[contains(text(), '03')] | " +
                                                                            "//span[contains(text(), '+92')] | " +
                                                                            "//div[contains(text(), '03')]")

                                    if phone_elems:
                                        contact_number = phone_elems[0].text.strip()
                                        break
                        except Exception:
                            continue
            except Exception:
                pass

            # Check for "SUPER HOT" or other urgency indicators
            is_hot = False
            try:
                hot_elems = self.driver.find_elements(By.XPATH,
                                                      "//*[contains(text(), 'SUPER HOT')] | " +
                                                      "//*[contains(@class, 'ae84a87a')] | " +
                                                      "//*[contains(text(), 'Featured')]")
                is_hot = len(hot_elems) > 0
            except Exception:
                pass

            # Create property data
            property_data = {
                'title': title,
                'price': price,
                'location': location,
                'description': description,
                'listing_url': url,
                'source': 'Zameen.com',
                'urgency': "HIGH" if is_hot else self._extract_urgency(f"{title} {description}"),
                'property_type': property_type,
                'size': size,
                'seller_name': seller_name,
                'contact_number': contact_number
            }

            print(f"Extracted detailed data for: {title}")
            return property_data

        except Exception as e:
            logger.error(f"Error getting Zameen.com listing details: {e}")
            return None

    def save_listings_to_db(self, listings):
        """Save listings to database"""
        saved_count = 0

        for listing in listings:
            try:
                # Make sure we only have the fields that exist in the database
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

                lead_id = self.db.add_lead(lead_data)
                if lead_id:
                    saved_count += 1
                    logger.info(f"Saved listing to database with ID {lead_id}: {listing['title']}")
                    print(f"Saved: {listing['title']} - {listing['price']}")
            except Exception as e:
                logger.error(f"Error saving listing to database: {str(e)}")
                print(f"Error adding lead: {str(e)}")

        return saved_count

    def run(self, olx_url, zameen_url):
        """Run the Selenium scraper on specified URLs"""
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

            return {
                'olx_count': len(olx_listings),
                'zameen_count': len(zameen_listings),
                'total_saved': total_saved,
                'urgent_count': len(urgent_leads),
                'urgent_leads': urgent_leads
            }

        finally:
            # Always close the driver to free resources
            self.close_driver()


if __name__ == "__main__":
    print("===== Selenium Real Estate Scraper =====")
    print("Scraping specific OLX and Zameen.com URLs using browser automation...")

    # Direct URLs to scrape
    olx_url = "https://www.olx.com.pk/islamabad_g4060615/land-plots_c40"
    zameen_url = "https://www.zameen.com/Plots/Islamabad-3-1.html"

    # Set headless=False to see the browser in action (good for debugging)
    # Set headless=True for production use without visible browser
    scraper = SeleniumScraper(headless=True)

    results = scraper.run(olx_url, zameen_url)

    print("\n===== Scraping Results =====")
    print(f"OLX Listings found: {results['olx_count']}")
    print(f"Zameen Listings found: {results['zameen_count']}")
    print(f"Total listings saved to database: {results['total_saved']}")
    print(f"Urgent leads found: {results['urgent_count']}")

    # Display some urgent leads if available
    if results['urgent_count'] > 0:
        print("\n===== Top Urgent Leads =====")
        for i, lead in enumerate(results['urgent_leads'][:5]):  # Show up to 5 urgent leads
            print(f"{i + 1}. {lead['title']}")
            print(f"   Price: {lead['price']}")
            print(f"   Location: {lead['location']}")
            print(f"   Size: {lead['size'] if 'size' in lead else 'N/A'}")
            print(f"   Contact: {lead['contact_number']}")
            print()

    print("=============================")