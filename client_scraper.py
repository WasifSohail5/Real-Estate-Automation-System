import requests
from bs4 import BeautifulSoup
import sqlite3
import re
from datetime import datetime
import time
import random
import json
import logging
from urllib.parse import urljoin, quote_plus
import undetected_chromedriver as uc
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
import fake_useragent

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("client_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# Database setup
def setup_client_database(db_path="client_scraping.db"):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create table for scraped clients data
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS scraped_clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        phone TEXT,
        preferred_location TEXT,
        min_budget REAL,
        max_budget REAL,
        min_size REAL,
        max_size REAL,
        size_unit TEXT DEFAULT 'marla',
        property_type TEXT,
        requirement_details TEXT,
        source_url TEXT,
        source_platform TEXT,
        scraped_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'new',
        processed INTEGER DEFAULT 0
    )
    ''')

    # Create table for tracking scraping sessions
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS scraping_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT,
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        records_found INTEGER DEFAULT 0,
        records_added INTEGER DEFAULT 0,
        status TEXT
    )
    ''')

    conn.commit()
    return conn


# Function to start tracking a scraping session
def start_scraping_session(conn, source):
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO scraping_sessions (source, start_time, status) VALUES (?, ?, ?)",
        (source, datetime.now(), "in_progress")
    )
    conn.commit()
    return cursor.lastrowid


# Function to complete a scraping session
def complete_scraping_session(conn, session_id, records_found, records_added, status="completed"):
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE scraping_sessions SET end_time = ?, records_found = ?, records_added = ?, status = ? WHERE id = ?",
        (datetime.now(), records_found, records_added, status, session_id)
    )
    conn.commit()


# Get random user agent
def get_random_user_agent():
    ua = fake_useragent.UserAgent()
    return ua.random


# Initialize undetected Chrome driver to bypass anti-bot measures
def get_undetected_chrome_driver(headless=True):
    options = uc.ChromeOptions()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"--user-agent={get_random_user_agent()}")

    driver = uc.Chrome(options=options, use_subprocess=True)
    return driver


# Regular Chrome driver with Selenium Wire for more options
def get_selenium_driver(headless=True, proxy=None):
    options = Options()
    if headless:
        options.add_argument("--headless")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    options.add_argument("--disable-extensions")
    options.add_argument(f"--user-agent={get_random_user_agent()}")

    if proxy:
        options.add_argument(f'--proxy-server={proxy}')

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    return driver


# Scrape OLX property wanted ads
def scrape_olx_wanted(conn):
    session_id = start_scraping_session(conn, "OLX")
    client_data = []

    try:
        logger.info("Starting OLX scraping...")
        driver = get_undetected_chrome_driver(headless=False)

        # OLX doesn't have a dedicated "wanted" section for properties
        # We'll search for keywords like "wanted" or "looking for" in the property section
        search_terms = [
            "wanted plot", "wanted house", "wanted flat",
            "looking for plot", "looking for house", "required plot"
        ]

        for term in search_terms:
            url = f"https://www.olx.com.pk/items/q-{quote_plus(term)}"
            logger.info(f"Searching OLX for: {term}")

            driver.get(url)
            time.sleep(random.uniform(3, 5))

            # Wait for listings to load
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-aut-id='itemBox']"))
                )
            except TimeoutException:
                logger.warning(f"Timeout waiting for OLX listings with term: {term}")
                continue

            # Scroll down to load more content
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

            # Extract listings
            listings = driver.find_elements(By.CSS_SELECTOR, "[data-aut-id='itemBox']")
            logger.info(f"Found {len(listings)} potential listings for term: {term}")

            for listing in listings:
                try:
                    title_element = listing.find_element(By.CSS_SELECTOR, "[data-aut-id='itemTitle']")
                    price_element = listing.find_element(By.CSS_SELECTOR, "[data-aut-id='itemPrice']")

                    # Get the listing URL to fetch more details
                    listing_url = listing.find_element(By.TAG_NAME, "a").get_attribute("href")

                    title = title_element.text
                    price_text = price_element.text

                    # Check if this is actually a request/wanted ad based on title
                    if any(keyword in title.lower() for keyword in
                           ["wanted", "looking", "need", "require", "searching"]):
                        # Visit the listing page to get more details
                        driver.execute_script("window.open('');")
                        driver.switch_to.window(driver.window_handles[1])
                        driver.get(listing_url)
                        time.sleep(random.uniform(2, 4))

                        # Extract detailed information
                        try:
                            description = driver.find_element(By.CSS_SELECTOR,
                                                              "[data-aut-id='itemDescriptionContent']").text
                        except NoSuchElementException:
                            description = ""

                        # Get seller info if available
                        try:
                            seller_name = driver.find_element(By.CSS_SELECTOR,
                                                              "[data-aut-id='profileCard'] [data-aut-id='profileName']").text
                        except NoSuchElementException:
                            seller_name = "Unknown"

                        # Combine all text for extraction
                        combined_text = f"{title} {description} {price_text}"

                        client = {
                            "name": seller_name,
                            "requirement_details": f"{title}\n{description}",
                            "source_url": listing_url,
                            "source_platform": "OLX",
                            "preferred_location": extract_location(combined_text),
                            "min_budget": extract_min_budget(combined_text) or extract_min_budget(price_text),
                            "max_budget": extract_max_budget(combined_text) or extract_max_budget(price_text),
                            "min_size": extract_min_size(combined_text),
                            "max_size": extract_max_size(combined_text),
                            "size_unit": extract_size_unit(combined_text),
                            "property_type": extract_property_type(combined_text),
                            "phone": extract_phone(combined_text),
                            "email": extract_email(combined_text)
                        }

                        client_data.append(client)

                        # Close the tab and switch back
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])
                        time.sleep(1)

                except Exception as e:
                    logger.error(f"Error processing OLX listing: {e}")
                    # Make sure we're back on the main window
                    if len(driver.window_handles) > 1:
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])

            # Add a delay between searches
            time.sleep(random.uniform(5, 10))

    except Exception as e:
        logger.error(f"Error during OLX scraping: {e}", exc_info=True)
        complete_scraping_session(conn, session_id, len(client_data), 0, "error")

    finally:
        if 'driver' in locals():
            driver.quit()

    # Save data to database
    added = 0
    if client_data:
        added = save_clients_to_db(conn, client_data)

    complete_scraping_session(conn, session_id, len(client_data), added)
    return client_data


# Scrape Property Groups on Facebook
def scrape_facebook_groups(conn, credentials=None):
    if not credentials:
        logger.warning("No Facebook credentials provided, skipping Facebook scraping")
        return []

    session_id = start_scraping_session(conn, "Facebook")
    client_data = []

    # List of property groups to scrape
    groups = [
        {"id": "islamabadproperties", "name": "Islamabad Properties"},
        {"id": "propertytalkhomesandplots", "name": "Property Talk Homes and Plots"},
        {"id": "plotsforsaleinislamabad", "name": "Plots for Sale in Islamabad"},
        {"id": "bahriaTownKarachiandIslamabad", "name": "Bahria Town Karachi and Islamabad"},
        {"id": "BahriaTown.Islbd.Rwp", "name": "Bahria Town Islamabad/Rawalpindi"}
    ]

    try:
        logger.info("Starting Facebook group scraping...")
        driver = get_undetected_chrome_driver(headless=False)

        # Login to Facebook
        driver.get("https://www.facebook.com/")
        time.sleep(3)

        # Accept cookies if prompted
        try:
            cookie_button = driver.find_element(By.XPATH,
                                                "//button[contains(., 'Allow all cookies') or contains(., 'Accept')]")
            cookie_button.click()
            time.sleep(1)
        except:
            pass

        # Enter credentials
        try:
            email_field = driver.find_element(By.ID, "email")
            password_field = driver.find_element(By.ID, "pass")

            email_field.send_keys(credentials.get('email', ''))
            password_field.send_keys(credentials.get('password', ''))

            login_button = driver.find_element(By.NAME, "login")
            login_button.click()

            # Wait for login to complete
            time.sleep(10)

            # Check if login was successful
            if "facebook.com/checkpoint" in driver.current_url:
                logger.error("Facebook login requires additional verification")
                return []

        except Exception as e:
            logger.error(f"Facebook login failed: {e}")
            return []

        # Process each group
        for group in groups:
            group_url = f"https://www.facebook.com/groups/{group['id']}"
            logger.info(f"Scraping Facebook group: {group['name']} ({group_url})")

            driver.get(group_url)
            time.sleep(random.uniform(5, 8))

            # Scroll to load more content
            for _ in range(10):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))

            # Look for posts
            posts = driver.find_elements(By.XPATH, "//div[contains(@data-pagelet, 'FeedUnit')]")

            logger.info(f"Found {len(posts)} posts in group {group['name']}")

            for post in posts:
                try:
                    # Get post text
                    post_text = ""
                    try:
                        post_text = post.find_element(By.XPATH, ".//div[@data-ad-comet-preview='message']").text
                    except:
                        try:
                            # Alternative selector
                            post_text = post.find_element(By.XPATH, ".//div[contains(@class, 'ecm0bbzt')]").text
                        except:
                            continue

                    # Check if this is a property wanted/needed post
                    keywords = ["wanted", "looking", "need", "require", "search", "find me", "seeking"]
                    property_terms = ["plot", "house", "home", "apartment", "flat", "property", "commercial",
                                      "residential"]

                    is_wanted_post = any(keyword in post_text.lower() for keyword in keywords) and \
                                     any(term in post_text.lower() for term in property_terms)

                    if is_wanted_post:
                        # Try to get post author
                        try:
                            author = post.find_element(By.XPATH,
                                                       ".//a[@role='link' and contains(@href, '/user/') or contains(@href, '/profile.php')]").text
                        except:
                            author = "Unknown User"

                        # Create client record
                        client = {
                            "name": author,
                            "requirement_details": post_text,
                            "source_url": group_url,
                            "source_platform": f"Facebook - {group['name']}",
                            "preferred_location": extract_location(post_text),
                            "min_budget": extract_min_budget(post_text),
                            "max_budget": extract_max_budget(post_text),
                            "min_size": extract_min_size(post_text),
                            "max_size": extract_max_size(post_text),
                            "size_unit": extract_size_unit(post_text),
                            "property_type": extract_property_type(post_text),
                            "phone": extract_phone(post_text),
                            "email": extract_email(post_text)
                        }

                        client_data.append(client)

                except Exception as e:
                    logger.error(f"Error processing Facebook post: {e}")

            # Add delay between groups
            time.sleep(random.uniform(10, 15))

    except Exception as e:
        logger.error(f"Error during Facebook scraping: {e}", exc_info=True)
        complete_scraping_session(conn, session_id, len(client_data), 0, "error")

    finally:
        if 'driver' in locals():
            driver.quit()

    # Save data to database
    added = 0
    if client_data:
        added = save_clients_to_db(conn, client_data)

    complete_scraping_session(conn, session_id, len(client_data), added)
    return client_data


# Scrape Zameen.com "Wanted" section
def scrape_zameen_wanted(conn):
    session_id = start_scraping_session(conn, "Zameen.com")
    client_data = []

    try:
        logger.info("Starting Zameen.com wanted ads scraping...")

        headers = {
            "User-Agent": get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Cache-Control": "max-age=0",
        }

        # Use Selenium for better handling of dynamic content
        driver = get_selenium_driver(headless=False)

        # Zameen.com Wanted section pages
        base_url = "https://www.zameen.com/Wanted/"

        # Navigate to the wanted section
        driver.get(base_url)
        time.sleep(random.uniform(3, 5))

        # Process multiple pages
        for page in range(1, 8):  # First 7 pages
            if page > 1:
                page_url = f"{base_url}index-{page}.html"
                driver.get(page_url)
                time.sleep(random.uniform(3, 5))

            logger.info(f"Processing Zameen.com wanted ads page {page}")

            # Wait for listings to load
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "li.ef447dde"))
                )
            except TimeoutException:
                logger.warning(f"Timeout waiting for Zameen.com listings on page {page}")
                # Try with different selector
                try:
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "li._357a9937"))
                    )
                    logger.info("Found listings with alternate selector")
                except TimeoutException:
                    logger.warning(f"Could not find listings on page {page}")
                    continue

            # Extract listings
            # Try different selectors as Zameen.com might change their class names
            listings = []
            for selector in ["li.ef447dde", "li._357a9937", "ul.c0df3811 > li"]:
                listings = driver.find_elements(By.CSS_SELECTOR, selector)
                if listings:
                    logger.info(f"Found {len(listings)} listings with selector {selector}")
                    break

            for listing in listings:
                try:
                    # Get listing title
                    title = ""
                    for title_selector in [".c0df3811", "._7ac32433", "h2"]:
                        try:
                            title_elem = listing.find_element(By.CSS_SELECTOR, title_selector)
                            title = title_elem.text
                            break
                        except NoSuchElementException:
                            continue

                    # Get description
                    description = ""
                    for desc_selector in [".f7065f07", "._162e6469", ".description"]:
                        try:
                            desc_elem = listing.find_element(By.CSS_SELECTOR, desc_selector)
                            description = desc_elem.text
                            break
                        except NoSuchElementException:
                            continue

                    # Get link to full listing
                    link = ""
                    try:
                        link_elem = listing.find_element(By.TAG_NAME, "a")
                        link = link_elem.get_attribute("href")
                    except NoSuchElementException:
                        pass

                    if title or description:
                        combined_text = f"{title} {description}"

                        client = {
                            "name": "Zameen User",  # Actual name usually not available in listings
                            "requirement_details": f"{title}\n{description}",
                            "source_url": link or base_url,
                            "source_platform": "Zameen.com",
                            "preferred_location": extract_location(combined_text),
                            "min_budget": extract_min_budget(combined_text),
                            "max_budget": extract_max_budget(combined_text),
                            "min_size": extract_min_size(combined_text),
                            "max_size": extract_max_size(combined_text),
                            "size_unit": extract_size_unit(combined_text),
                            "property_type": extract_property_type(combined_text),
                            "phone": extract_phone(combined_text),
                            "email": extract_email(combined_text)
                        }

                        client_data.append(client)

                except Exception as e:
                    logger.error(f"Error processing Zameen listing: {e}")

            # Add delay between pages
            time.sleep(random.uniform(5, 8))

    except Exception as e:
        logger.error(f"Error during Zameen.com scraping: {e}", exc_info=True)
        complete_scraping_session(conn, session_id, len(client_data), 0, "error")

    finally:
        if 'driver' in locals():
            driver.quit()

    # Save data to database
    added = 0
    if client_data:
        added = save_clients_to_db(conn, client_data)

    complete_scraping_session(conn, session_id, len(client_data), added)
    return client_data


# Scrape Graana.com property listings
def scrape_graana(conn):
    session_id = start_scraping_session(conn, "Graana.com")
    client_data = []

    try:
        logger.info("Starting Graana.com scraping...")
        driver = get_selenium_driver(headless=False)

        # Graana doesn't have a direct "wanted" section, so we'll check their regular listings
        # and filter by description to find potential buyers/renters
        cities = ["islamabad", "rawalpindi", "lahore", "karachi"]

        for city in cities:
            # For rent
            url = f"https://www.graana.com/rent/property/{city}"
            driver.get(url)
            time.sleep(random.uniform(4, 6))

            logger.info(f"Scraping Graana.com {city} rental listings")

            # Wait for listings to load
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".tn-property-card"))
                )
            except TimeoutException:
                logger.warning(f"Timeout waiting for Graana.com listings for {city}")
                continue

            # Scroll to load more
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)

            # Extract listings
            listings = driver.find_elements(By.CSS_SELECTOR, ".tn-property-card")

            for listing in listings:
                try:
                    title_elem = listing.find_element(By.CSS_SELECTOR, ".tn-property-card-title")
                    price_elem = listing.find_element(By.CSS_SELECTOR, ".tn-property-card-price")
                    location_elem = listing.find_element(By.CSS_SELECTOR, ".tn-property-card-location")

                    title = title_elem.text
                    price = price_elem.text
                    location = location_elem.text

                    # Get link
                    link = listing.find_element(By.TAG_NAME, "a").get_attribute("href")

                    # Visit listing page for more details
                    driver.execute_script("window.open('');")
                    driver.switch_to.window(driver.window_handles[1])
                    driver.get(link)
                    time.sleep(random.uniform(2, 4))

                    # Get description
                    description = ""
                    try:
                        description = driver.find_element(By.CSS_SELECTOR, ".tn-property-description").text
                    except:
                        description = ""

                    # Extract seller info
                    seller_name = "Graana User"
                    try:
                        seller_elem = driver.find_element(By.CSS_SELECTOR, ".tn-property-owner-name")
                        seller_name = seller_elem.text
                    except:
                        pass

                    # Only include if there's indication this is someone looking for property
                    # (most Graana listings are sellers, not buyers)
                    combined_text = f"{title} {description} {location}"
                    buyer_keywords = ["looking for", "want to buy", "want to rent", "need a", "searching for"]

                    if any(keyword in combined_text.lower() for keyword in buyer_keywords):
                        client = {
                            "name": seller_name,
                            "requirement_details": f"{title}\n{description}",
                            "source_url": link,
                            "source_platform": "Graana.com",
                            "preferred_location": location or extract_location(combined_text),
                            "min_budget": extract_min_budget(combined_text) or extract_min_budget(price),
                            "max_budget": extract_max_budget(combined_text) or extract_max_budget(price),
                            "min_size": extract_min_size(combined_text),
                            "max_size": extract_max_size(combined_text),
                            "size_unit": extract_size_unit(combined_text),
                            "property_type": extract_property_type(combined_text),
                            "phone": extract_phone(combined_text),
                            "email": extract_email(combined_text)
                        }

                        client_data.append(client)

                    # Close tab and return to main
                    driver.close()
                    driver.switch_to.window(driver.window_handles[0])

                except Exception as e:
                    logger.error(f"Error processing Graana listing: {e}")
                    # Make sure we're back on the main window
                    if len(driver.window_handles) > 1:
                        driver.close()
                        driver.switch_to.window(driver.window_handles[0])

            # Add delay between cities
            time.sleep(random.uniform(8, 12))

    except Exception as e:
        logger.error(f"Error during Graana.com scraping: {e}", exc_info=True)
        complete_scraping_session(conn, session_id, len(client_data), 0, "error")

    finally:
        if 'driver' in locals():
            driver.quit()

    # Save data to database
    added = 0
    if client_data:
        added = save_clients_to_db(conn, client_data)

    complete_scraping_session(conn, session_id, len(client_data), added)
    return client_data


# Scrape property forums like Pakistan Defence Forum real estate sections
def scrape_property_forums(conn):
    session_id = start_scraping_session(conn, "Property Forums")
    client_data = []

    try:
        logger.info("Starting property forums scraping...")
        headers = {
            "User-Agent": get_random_user_agent(),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://www.google.com/",
            "Connection": "keep-alive"
        }

        # Pakistan Defence Forum real estate section
        forum_url = "https://defence.pk/pdf/forums/real-estate.142/"

        response = requests.get(forum_url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')

            # Find forum threads
            threads = soup.select(".structItem--thread")

            logger.info(f"Found {len(threads)} threads in property forum")

            for thread in threads:
                try:
                    title_elem = thread.select_one(".structItem-title")
                    if not title_elem:
                        continue

                    title = title_elem.text.strip()
                    thread_url = urljoin(forum_url, title_elem.find("a")["href"])

                    # Check if this might be a buying/looking for post
                    buy_keywords = ["wtb", "looking", "want", "need", "searching", "required", "requirement"]

                    if any(keyword in title.lower() for keyword in buy_keywords):
                        # Get thread content
                        thread_response = requests.get(thread_url, headers=headers)
                        if thread_response.status_code != 200:
                            continue

                        thread_soup = BeautifulSoup(thread_response.content, 'html.parser')

                        # Get first post content (original post)
                        first_post = thread_soup.select_one(".message-inner")
                        if not first_post:
                            continue

                        content = first_post.select_one(".message-body .bbWrapper")
                        if not content:
                            continue

                        post_text = content.text.strip()

                        # Get author
                        author = "Forum User"
                        author_elem = thread_soup.select_one(".message-name")
                        if author_elem:
                            author = author_elem.text.strip()

                        combined_text = f"{title} {post_text}"

                        client = {
                            "name": author,
                            "requirement_details": f"{title}\n{post_text}",
                            "source_url": thread_url,
                            "source_platform": "Defence.pk Forum",
                            "preferred_location": extract_location(combined_text),
                            "min_budget": extract_min_budget(combined_text),
                            "max_budget": extract_max_budget(combined_text),
                            "min_size": extract_min_size(combined_text),
                            "max_size": extract_max_size(combined_text),
                            "size_unit": extract_size_unit(combined_text),
                            "property_type": extract_property_type(combined_text),
                            "phone": extract_phone(combined_text),
                            "email": extract_email(combined_text)
                        }

                        client_data.append(client)

                    # Add delay between thread requests
                    time.sleep(random.uniform(1, 3))

                except Exception as e:
                    logger.error(f"Error processing forum thread: {e}")
        else:
            logger.error(f"Failed to access forum: {response.status_code}")

    except Exception as e:
        logger.error(f"Error during forum scraping: {e}", exc_info=True)
        complete_scraping_session(conn, session_id, len(client_data), 0, "error")

    # Save data to database
    added = 0
    if client_data:
        added = save_clients_to_db(conn, client_data)

    complete_scraping_session(conn, session_id, len(client_data), added)
    return client_data


# Enhanced extraction functions
def extract_location(text):
    if not text:
        return None

    text = text.lower()

    # Major cities and areas in Pakistan
    locations = [
        # Major cities
        "islamabad", "rawalpindi", "lahore", "karachi", "peshawar", "quetta", "faisalabad",
        "multan", "gujranwala", "sialkot", "hyderabad",

        # Popular areas/housing schemes
        "bahria town", "dha", "gulberg", "wapda town", "johar town", "askari", "gulshan-e-iqbal",
        "north nazimabad", "f-", "e-", "g-", "i-", "h-", "blue area", "satellite town",
        "cantt", "cantonment", "model town", "garden town", "valencia", "pwd", "capital smart city",
        "park view city", "gulshan-e-jinnah", "soan garden", "bani gala", "cda sector"
    ]

    # First try regex patterns for specific location mentions
    location_patterns = [
        r'(?:in|at|near|around|)\s+([a-zA-Z0-9\s\-,]+(?:phase|sector|block)[a-zA-Z0-9\s\-,]*)',
        r'(?:in|at|near|around|)\s+([a-zA-Z0-9\s\-,]+(?:town|housing|society|colony|garden|view)[a-zA-Z0-9\s\-,]*)',
        r'(?:in|at|near|around|)\s+([a-zA-Z0-9\s\-,]+(?:DHA|CDA|WAPDA)[a-zA-Z0-9\s\-,]*)',
        r'(?:location|area|place|locality)(?:[\s:]*)((?:[a-zA-Z0-9\s\-,])+)'
    ]

    for pattern in location_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            location = match.group(1).strip()
            # Clean up the match
            location = re.sub(r'[^\w\s\-,]', '', location).strip()
            return location[:50]  # Limit length

    # Then check for known locations
    for loc in locations:
        if loc in text:
            # Try to get surrounding context
            pattern = re.compile(r'(?:[\w\s]{0,20})(' + re.escape(loc) + r'(?:[\w\s]{0,30}))', re.IGNORECASE)
            match = pattern.search(text)
            if match:
                context = match.group(1).strip()
                # Clean up and standardize
                context = re.sub(r'[^\w\s\-,]', '', context).strip()
                return context[:50]  # Limit length
            return loc.title()

    return None


def extract_min_budget(text):
    if not text:
        return None

    text = text.lower()

    # Multiple patterns for different formats
    budget_patterns = [
        # Format: "budget is 50-60 lacs"
        r'(?:budget|price|amount|cost|range|rs\.?|pkr)[:\s]*(?:is|of|around|approximately)?[:\s]*(?:rs\.?|pkr)?\s*(\d+(?:\.\d+)?)\s*(?:-|to|and|or|lac|lakh|crore|million|cr|k)',

        # Format: "50-60 lac budget"
        r'(\d+(?:\.\d+)?)\s*(?:-|to|and|or)\s*\d+(?:\.\d+)?\s*(?:lac|lakh|crore|million|cr|k|)\s*(?:budget|price|amount|cost|range|rs\.?|pkr)',

        # Format: "50 lac budget"
        r'(\d+(?:\.\d+)?)\s*(?:lac|lakh|crore|million|cr|k)\s*(?:budget|price|amount|cost|range|rs\.?|pkr)',

        # Format: "budget 50 lac"
        r'(?:budget|price|amount|cost|range)[:\s]*(?:rs\.?|pkr)?\s*(\d+(?:\.\d+)?)\s*(?:lac|lakh|crore|million|cr|k)'
    ]

    for pattern in budget_patterns:
        match = re.search(pattern, text)
        if match:
            value = float(match.group(1))

            # Determine multiplier based on context
            if "crore" in text or "cr" in text:
                multiplier = 10000000  # 1 crore = 10 million PKR
            elif "lac" in text or "lakh" in text:
                multiplier = 100000  # 1 lac = 100,000 PKR
            elif "million" in text:
                multiplier = 1000000  # 1 million = 1,000,000 PKR
            elif "k" in text and value > 10:  # Only consider k if value is reasonable
                multiplier = 1000  # 1k = 1,000 PKR
            else:
                # If no unit specified but value is small, assume it's in lacs/lakhs
                if value < 100:
                    multiplier = 100000
                else:
                    multiplier = 1

            return value * multiplier

    return None


def extract_max_budget(text):
    if not text:
        return None

    text = text.lower()

    # Multiple patterns for different formats
    budget_patterns = [
        # Format: "budget is 50-60 lacs"
        r'(?:budget|price|amount|cost|range|rs\.?|pkr)[:\s]*(?:is|of|around|approximately)?[:\s]*(?:rs\.?|pkr)?\s*\d+(?:\.\d+)?\s*(?:-|to|and|or)\s*(\d+(?:\.\d+)?)\s*(?:lac|lakh|crore|million|cr|k)',

        # Format: "50-60 lac budget"
        r'\d+(?:\.\d+)?\s*(?:-|to|and|or)\s*(\d+(?:\.\d+)?)\s*(?:lac|lakh|crore|million|cr|k|)\s*(?:budget|price|amount|cost|range|rs\.?|pkr)',

        # Format: just find a number after "lac/lakh/crore" if no range is specified
        r'(?:upto|maximum|max|around)\s*(?:rs\.?|pkr)?\s*(\d+(?:\.\d+)?)\s*(?:lac|lakh|crore|million|cr|k)'
    ]

    for pattern in budget_patterns:
        match = re.search(pattern, text)
        if match:
            value = float(match.group(1))

            # Determine multiplier based on context
            if "crore" in text or "cr" in text:
                multiplier = 10000000  # 1 crore = 10 million PKR
            elif "lac" in text or "lakh" in text:
                multiplier = 100000  # 1 lac = 100,000 PKR
            elif "million" in text:
                multiplier = 1000000  # 1 million = 1,000,000 PKR
            elif "k" in text and value > 10:  # Only consider k if value is reasonable
                multiplier = 1000  # 1k = 1,000 PKR
            else:
                # If no unit specified but value is small, assume it's in lacs/lakhs
                if value < 100:
                    multiplier = 100000
                else:
                    multiplier = 1

            return value * multiplier

    # If no max found but min exists, use min as max too (for single value budgets)
    min_budget = extract_min_budget(text)
    if min_budget:
        return min_budget

    return None


def extract_min_size(text):
    if not text:
        return None

    text = text.lower()

    # Multiple patterns for different formats
    size_patterns = [
        # Format: "size is 5-10 marla"
        r'(?:size|area|plot)[:\s]*(?:is|of|around|approximately)?[:\s]*(\d+(?:\.\d+)?)\s*(?:-|to|and|or)',

        # Format: "5-10 marla plot"
        r'(\d+(?:\.\d+)?)\s*(?:-|to|and|or)\s*\d+(?:\.\d+)?\s*(?:marla|kanal|sq\.?ft|square feet|sq yards|square yards)',

        # Format: "5 marla plot"
        r'(\d+(?:\.\d+)?)\s*(?:marla|kanal|sq\.?ft|square feet|sq yards|square yards)'
    ]

    for pattern in size_patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))

    return None


def extract_max_size(text):
    if not text:
        return None

    text = text.lower()

    # Multiple patterns for different formats
    size_patterns = [
        # Format: "size is 5-10 marla"
        r'(?:size|area|plot)[:\s]*(?:is|of|around|approximately)?[:\s]*\d+(?:\.\d+)?\s*(?:-|to|and|or)\s*(\d+(?:\.\d+)?)',

        # Format: "5-10 marla plot"
        r'\d+(?:\.\d+)?\s*(?:-|to|and|or)\s*(\d+(?:\.\d+)?)\s*(?:marla|kanal|sq\.?ft|square feet|sq yards|square yards)'
    ]

    for pattern in size_patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1))

    # If no max found but min exists, use min as max too (for single value sizes)
    min_size = extract_min_size(text)
    if min_size:
        return min_size

    return None


def extract_size_unit(text):
    if not text:
        return "marla"  # Default

    text = text.lower()

    if "kanal" in text:
        return "kanal"
    elif "marla" in text:
        return "marla"
    elif "square yard" in text or "sq yard" in text or "sq yd" in text:
        return "sq yards"
    elif "square feet" in text or "sq ft" in text or "sq feet" in text:
        return "sq ft"
    elif "acre" in text:
        return "acre"
    else:
        return "marla"  # Default in Pakistan


def extract_property_type(text):
    if not text:
        return "Residential"  # Default

    text = text.lower()

    # Check for plot/land
    if any(word in text for word in ["plot", "land", "file", "possession", "property file"]):
        if "commercial" in text:
            return "Commercial Plot"
        elif "agricultural" in text or "farm" in text:
            return "Agricultural Land"
        else:
            return "Residential Plot"

    # Check for house/villa
    elif any(word in text for word in ["house", "home", "villa", "bungalow", "kothi"]):
        if "commercial" in text:
            return "Commercial Building"
        else:
            return "House"

    # Check for flat/apartment
    elif any(word in text for word in ["flat", "apartment", "portion", "floor"]):
        return "Apartment"

    # Check for commercial
    elif any(word in text for word in ["commercial", "shop", "office", "plaza", "market", "retail"]):
        if "shop" in text:
            return "Shop"
        elif "office" in text:
            return "Office"
        else:
            return "Commercial"

    # Default
    else:
        return "Residential"


def extract_phone(text):
    if not text:
        return None

    # Pakistan phone number patterns
    phone_patterns = [
        # Format: 03XX-XXXXXXX
        r'0?\s*3\d{2}[-\s]?\d{7}',

        # Format: +92 3XX XXXXXXX
        r'[\+]?92[-\s]?3\d{2}[-\s]?\d{7}',

        # Format: 3XX XXXXXXX (without leading 0 or +92)
        r'[^0-9]3\d{2}[-\s]?\d{7}[^0-9]',

        # Other common Pakistani formats
        r'0?\s*[4-9]\d{2}[-\s]?\d{7}'
    ]

    for pattern in phone_patterns:
        match = re.search(pattern, text)
        if match:
            phone = match.group(0)
            # Clean up the number
            phone = re.sub(r'[^0-9+]', '', phone)

            # Standardize format
            if phone.startswith('+'):
                return phone
            elif phone.startswith('92'):
                return f"+{phone}"
            elif phone.startswith('03'):
                return f"+92{phone[1:]}"
            elif phone.startswith('3') and len(phone) == 10:
                return f"+92{phone}"
            else:
                return phone

    return None


def extract_email(text):
    if not text:
        return None

    email_pattern = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
    match = email_pattern.search(text)

    if match:
        return match.group(0)

    return None


def save_clients_to_db(conn, clients):
    cursor = conn.cursor()
    added_count = 0

    for client in clients:
        # Clean up any None values to avoid DB errors
        clean_client = {k: (v if v is not None else "") for k, v in client.items()}

        # Check if this client already exists (based on combination of factors)
        if 'requirement_details' in clean_client and clean_client['requirement_details']:
            # Check for duplicate based on content
            cursor.execute('''
                SELECT id FROM scraped_clients 
                WHERE requirement_details = ? OR 
                      (phone = ? AND phone != '') OR
                      (email = ? AND email != '')
            ''', (
                clean_client.get('requirement_details', ""),
                clean_client.get('phone', ""),
                clean_client.get('email', "")
            ))

            if cursor.fetchone():
                continue  # Skip this client as it already exists

        # Insert into database
        cursor.execute('''
        INSERT INTO scraped_clients 
        (name, email, phone, preferred_location, min_budget, max_budget, min_size, max_size, size_unit, 
        property_type, requirement_details, source_url, source_platform, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            clean_client.get('name', "Unknown"),
            clean_client.get('email', ""),
            clean_client.get('phone', ""),
            clean_client.get('preferred_location', ""),
            clean_client.get('min_budget', 0),
            clean_client.get('max_budget', 0),
            clean_client.get('min_size', 0),
            clean_client.get('max_size', 0),
            clean_client.get('size_unit', "marla"),
            clean_client.get('property_type', "Residential"),
            clean_client.get('requirement_details', ""),
            clean_client.get('source_url', ""),
            clean_client.get('source_platform', ""),
            "new"
        ))

        added_count += 1

    conn.commit()
    logger.info(f"Saved {added_count} new client records to database (out of {len(clients)} found)")
    return added_count


def main():
    logger.info("=" * 80)
    logger.info("Real Estate Client Data Scraper - Enhanced Edition")
    logger.info("=" * 80)
    logger.info(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Setup database
    conn = setup_client_database()

    try:
        # Dictionary to store results from each source
        results = {}

        # 1. Scrape OLX
        logger.info("\nStarting OLX scraping...")
        olx_clients = scrape_olx_wanted(conn)
        results["OLX"] = len(olx_clients)

        # 2. Scrape Zameen.com
        logger.info("\nStarting Zameen.com scraping...")
        zameen_clients = scrape_zameen_wanted(conn)
        results["Zameen.com"] = len(zameen_clients)

        # 3. Scrape Graana.com
        logger.info("\nStarting Graana.com scraping...")
        graana_clients = scrape_graana(conn)
        results["Graana.com"] = len(graana_clients)

        # 4. Scrape property forums
        logger.info("\nStarting property forums scraping...")
        forum_clients = scrape_property_forums(conn)
        results["Property Forums"] = len(forum_clients)

        # 5. Facebook scraping (requires login)
        logger.info("\nSkipping Facebook scraping (requires credentials)")
        # If you have credentials:
        # fb_credentials = {
        #     "email": "your_email@example.com",
        #     "password": "your_password"
        # }
        # fb_clients = scrape_facebook_groups(conn, fb_credentials)
        # results["Facebook"] = len(fb_clients)

        # Summary
        logger.info("\nScraping summary:")
        total_clients = sum(results.values())
        for source, count in results.items():
            logger.info(f"- {source}: {count} clients found")
        logger.info(f"Total clients found: {total_clients}")

        # Show database statistics
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM scraped_clients")
        total_in_db = cursor.fetchone()[0]
        logger.info(f"Total clients in database: {total_in_db}")

        logger.info("\nScraping completed successfully!")

    except Exception as e:
        logger.error(f"Error in main scraping process: {e}", exc_info=True)

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()