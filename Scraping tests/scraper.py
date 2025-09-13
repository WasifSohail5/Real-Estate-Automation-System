import logging
import requests
import time
import random
import re
from bs4 import BeautifulSoup
from database_operations import DatabaseManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('scraper.log'), logging.StreamHandler()]
)
logger = logging.getLogger('direct_scraper')


class DirectScraper:
    """Direct scraper for specific OLX and Zameen URLs"""

    def __init__(self):
        self.db = DatabaseManager()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1"
        }

    def _get_page(self, url):
        """Get webpage content"""
        try:
            # Add small random delay to avoid being blocked
            time.sleep(random.uniform(1, 3))

            logger.info(f"Fetching URL: {url}")
            response = requests.get(url, headers=self.headers, timeout=15)

            if response.status_code != 200:
                logger.warning(f"Failed to load page: {url} - Status {response.status_code}")
                return None

            return response.text
        except Exception as e:
            logger.error(f"Error fetching URL {url}: {e}")
            return None

    def _extract_urgency(self, text):
        """Extract urgency level from listing text"""
        if not text:
            return "NORMAL"

        text = text.lower()
        high_urgency_keywords = [
            "urgent", "urgently", "immediate", "quick sale", "quick deal",
            "fast sale", "hurry", "asap", "bargain", "distress", "must sell",
            "leaving city", "leaving country", "featured", "super hot"
        ]

        medium_urgency_keywords = [
            "good deal", "great deal", "negotiable", "price reduced",
            "below market", "motivated", "open to offers", "hot"
        ]

        if any(keyword in text for keyword in high_urgency_keywords):
            return "HIGH"
        elif any(keyword in text for keyword in medium_urgency_keywords):
            return "MEDIUM"
        else:
            return "NORMAL"

    def scrape_olx(self, url):
        """Scrape property listings from OLX"""
        all_listings = []
        html_content = self._get_page(url)

        if not html_content:
            return []

        soup = BeautifulSoup(html_content, 'html.parser')

        # Based on your screenshot, find the listing container
        main_container = soup.select_one('div[aria-label="Listings"]')
        if not main_container:
            logger.warning("Could not find main listings container on OLX")
            # Try an alternative approach - look for all listing cards
            listings = soup.select('li[data-testid="listing-card"], li.EIR5N, div[data-aut-id="itemBox"]')
            if not listings:
                logger.warning("Could not find any listing cards on OLX")
                return []
            logger.info(f"Found {len(listings)} OLX listings using fallback selector")
        else:
            # Find all listing cards within the main container
            listings = main_container.select('li[data-cy="l-card"], li.EIR5N, div.EIR5N')
            logger.info(f"Found {len(listings)} OLX listings in main container")

        # Process each listing
        for listing in listings:
            try:
                # Get the listing link
                link_elem = listing.select_one('a[href]')
                if not link_elem:
                    continue

                listing_url = link_elem['href']
                if not listing_url.startswith('http'):
                    listing_url = f"https://www.olx.com.pk{listing_url}"

                # Get title - Based on your screenshot
                title = None
                title_elem = listing.select_one('div[aria-label="Title"]')
                if title_elem:
                    title = title_elem.text.strip()
                else:
                    # Try alternatives
                    for title_selector in ['h2', '.Text_Text__text__RRpw7', 'span.Text_Text__text__RRpw7',
                                           '[data-aut-id="itemTitle"]']:
                        title_elem = listing.select_one(title_selector)
                        if title_elem:
                            title = title_elem.text.strip()
                            break

                if not title:
                    logger.warning("Could not extract title from OLX listing")
                    continue

                # Get price - Based on your screenshot
                price = 'N/A'
                price_elem = listing.select_one('div[aria-label="Price"]')
                if price_elem:
                    price = price_elem.text.strip()
                else:
                    # Try alternatives
                    for price_selector in ['span[data-aut-id="itemPrice"]',
                                           '.Text_Text__text__RRpw7.Text_Text__weight_500__ygTvF']:
                        price_elem = listing.select_one(price_selector)
                        if price_elem:
                            price = price_elem.text.strip()
                            break

                # Get location - Based on your screenshot
                location_text = 'Islamabad'
                location_elem = listing.select_one('div[aria-label="Location"]')
                if location_elem:
                    location_text = location_elem.text.strip()
                else:
                    # Try alternatives
                    for location_selector in ['span[data-aut-id="item-location"]',
                                              '.Text_Text__text__RRpw7.Text_Text__subtle__nO5Rj']:
                        location_elem = listing.select_one(location_selector)
                        if location_elem:
                            location_text = location_elem.text.strip()
                            break

                # Get property size information
                size = 'N/A'
                size_elem = listing.select_one('span[aria-label="Size"]')
                if size_elem:
                    size = size_elem.text.strip()
                else:
                    # Try to extract size from title
                    size_match = re.search(r'(\d+)\s*marla|\d+\s*kanal', title.lower())
                    if size_match:
                        size = size_match.group(0)

                # Get featured status
                is_featured = False
                featured_elem = listing.select_one('.Featured_featured__VJm85, span[data-aut-id="featured-tag"]')
                if featured_elem:
                    is_featured = True

                # Create description combining available info
                description = f"{title}. Located in {location_text}. {size} land."

                # Determine urgency based on featured status and keywords
                urgency = "HIGH" if is_featured else self._extract_urgency(f"{title} {description}")

                # Create listing data
                property_data = {
                    'title': title,
                    'price': price,
                    'location': location_text,
                    'description': description,
                    'listing_url': listing_url,
                    'source': 'OLX',
                    'urgency': urgency,
                    'property_type': 'Plot',
                    'size': size
                }

                logger.info(f"Extracted OLX listing: {title} - {price}")
                all_listings.append(property_data)

            except Exception as e:
                logger.error(f"Error extracting OLX listing: {str(e)}")
                continue

        logger.info(f"Successfully extracted {len(all_listings)} listings from OLX")
        return all_listings

    def scrape_zameen(self, url):
        """Scrape property listings from Zameen.com"""
        all_listings = []
        html_content = self._get_page(url)

        if not html_content:
            return []

        soup = BeautifulSoup(html_content, 'html.parser')

        # Based on your screenshot, find property cards
        listings = soup.select('article.card, li[role="article"], div._357a9937')

        if not listings:
            # Try alternative selectors
            listings = soup.select('div[aria-label="Listing"], div.ef447dde, article')

        logger.info(f"Found {len(listings)} Zameen listings using selector")

        # Process each listing
        for listing in listings:
            try:
                # Get the listing URL
                link_elem = listing.select_one('a.b7880daf, a._7ac32433, a[href*="/Property/"]')

                if not link_elem:
                    # Try finding any link
                    link_elem = listing.select_one('a[href]')

                if not link_elem:
                    logger.warning("Could not find link in Zameen listing")
                    continue

                listing_url = link_elem['href']
                if not listing_url.startswith('http'):
                    listing_url = f"https://www.zameen.com{listing_url}"

                # Get price
                price = 'N/A'
                price_elem = listing.select_one('span.f343d9ce, span.c4fc20ba, div.cfc44b47')
                if price_elem:
                    price = price_elem.text.strip()

                # Get title
                title = None
                title_elem = listing.select_one('h2.c21a3f5e, h2, div.c21a3f5e')
                if title_elem:
                    title = title_elem.text.strip()

                if not title:
                    logger.warning("Could not extract title from Zameen listing")
                    continue

                # Get location
                location_text = 'Islamabad'
                location_elem = listing.select_one('div._162e6469, div.cfc44b47 + div')
                if location_elem:
                    location_text = location_elem.text.strip()

                # Get property size
                size = 'N/A'
                size_elem = listing.select_one('div[aria-label="Area"] span, span.b1a784e2')
                if size_elem:
                    size = size_elem.text.strip()
                else:
                    # Try to extract from title
                    size_match = re.search(r'(\d+)\s*marla|\d+\s*kanal|\d+\s*sq(uare)?\s*(ft|yd|yard|feet|foot)',
                                           title.lower())
                    if size_match:
                        size = size_match.group(0)

                # Check if it's a featured/hot listing
                is_featured = False
                featured_elem = listing.select_one('div.d6e81fd0, div.aeea0330, span.SUPER.HOT')
                if featured_elem:
                    is_featured = True

                # Create description combining available info
                description = f"{title}. Located in {location_text}. {size} land."

                # Determine urgency based on featured status and keywords
                urgency = "HIGH" if is_featured else self._extract_urgency(f"{title} {description}")

                # Create property data
                property_data = {
                    'title': title,
                    'price': price,
                    'location': location_text,
                    'description': description,
                    'listing_url': listing_url,
                    'source': 'Zameen.com',
                    'urgency': urgency,
                    'property_type': 'Plot',
                    'size': size
                }

                logger.info(f"Extracted Zameen listing: {title} - {price}")
                all_listings.append(property_data)

            except Exception as e:
                logger.error(f"Error extracting Zameen listing: {str(e)}")
                continue

        logger.info(f"Successfully extracted {len(all_listings)} listings from Zameen")
        return all_listings

    def save_listings_to_db(self, listings):
        """Save listings to database"""
        saved_count = 0

        for listing in listings:
            try:
                lead_id = self.db.add_lead(listing)
                if lead_id:
                    saved_count += 1
                    logger.info(f"Saved listing to database with ID {lead_id}: {listing['title']}")
            except Exception as e:
                logger.error(f"Error saving listing to database: {str(e)}")

        return saved_count

    def run(self, olx_url, zameen_url):
        """Run the direct scraper on specified URLs"""
        total_saved = 0

        # Scrape OLX
        print("Starting OLX scraper...")
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


if __name__ == "__main__":
    print("===== Direct Real Estate Scraper =====")
    print("Scraping specific OLX and Zameen.com URLs...")

    # Direct URLs to scrape
    olx_url = "https://www.olx.com.pk/islamabad_g4060615/land-plots_c40"
    zameen_url = "https://www.zameen.com/Plots/Islamabad-3-1.html"

    scraper = DirectScraper()
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
            print(f"{i + 1}. {lead['title']} - {lead['price']} - {lead['location']}")

    print("=============================")