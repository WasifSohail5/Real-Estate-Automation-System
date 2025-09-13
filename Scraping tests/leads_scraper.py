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

    def scrape_olx(self, url):
        """Scrape property listings directly from OLX HTML source"""
        all_listings = []
        html_content = self._get_page(url)

        if not html_content:
            return []

        # First, try to extract using Beautiful Soup
        soup = BeautifulSoup(html_content, 'html.parser')

        # Look for listings container
        main_content = soup.select_one('#bodyContainer, div[aria-label="Listings"], div.EIR5N, div.ee2b0479')

        if not main_content:
            logger.warning("Could not find main content container on OLX")
            # Try a direct approach - search the HTML for patterns
            print("Using alternative approach for OLX...")
            return self._extract_olx_listings_from_html(html_content)

        # Try to find listings
        listings = main_content.select('li, div.EIR5N, div[aria-label="Listing"], a._2KkSl')

        if not listings:
            logger.warning("No listings found in main content")
            return self._extract_olx_listings_from_html(html_content)

        logger.info(f"Found {len(listings)} potential OLX listings")

        # Process each listing
        for listing in listings:
            try:
                # Skip if it doesn't contain any link
                if not listing.select_one('a'):
                    continue

                # Get listing URL
                link_elem = listing.select_one('a')
                listing_url = link_elem['href'] if link_elem and link_elem.has_attr('href') else ""
                if not listing_url:
                    continue

                if not listing_url.startswith('http'):
                    listing_url = f"https://www.olx.com.pk{listing_url}"

                # Look for key elements in the listing
                title_elem = None
                for elem in listing.select('span, h2, div'):
                    if elem.get_text().strip() and len(elem.get_text().strip()) > 15:
                        title_elem = elem
                        break

                if not title_elem:
                    continue

                title = title_elem.get_text().strip()

                # Extract price - look for text with Rs or PKR
                price = "N/A"
                for elem in listing.select('span, div'):
                    text = elem.get_text().strip()
                    if 'rs' in text.lower() or 'pkr' in text.lower() or 'lac' in text.lower() or 'crore' in text.lower():
                        price = text
                        break

                # Extract location
                location = "Islamabad"
                for elem in listing.select('span, div'):
                    text = elem.get_text().strip()
                    if len(text) > 3 and len(text) < 50 and text != title and text != price:
                        if 'islamabad' in text.lower() or 'sector' in text.lower() or 'phase' in text.lower():
                            location = text
                            break

                # Determine property size from title
                size = "N/A"
                size_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:marla|kanal|sq\.?\s*(?:ft|feet|yard|yd|meter|m))',
                                       title.lower())
                if size_match:
                    size = size_match.group(0)

                # Check if it's featured/urgent
                is_featured = False
                for elem in listing.select('span, div'):
                    if 'featured' in elem.get_text().lower() or 'super hot' in elem.get_text().lower():
                        is_featured = True
                        break

                # Create description
                description = f"{title}. Located in {location}."
                if size != "N/A":
                    description += f" {size} plot."

                # Determine urgency
                urgency = "HIGH" if is_featured else self._extract_urgency(title)

                # Create property data - ONLY INCLUDE FIELDS IN THE DATABASE
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
                    # Removed 'email' field
                }

                all_listings.append(property_data)
                print(f"Found OLX listing: {title}")

            except Exception as e:
                logger.error(f"Error processing OLX listing: {str(e)}")
                continue

        return all_listings

    def _extract_olx_listings_from_html(self, html_content):
        """Extract listings by parsing the raw HTML"""
        if not html_content:
            return []

        listings = []

        # Look for listing patterns in the HTML
        # OLX listings usually have title and price near each other
        title_price_blocks = re.findall(r'<[^>]+>([^<]{10,100})</[^>]+>[\s\S]{1,200}Rs\s*[\d,.]+', html_content)

        for i, block in enumerate(title_price_blocks):
            try:
                # Extract title from the matched block
                title = block.strip()

                # Find price near the title
                price_match = re.search(r'Rs\s*[\d,.]+',
                                        html_content[html_content.find(block):html_content.find(block) + 500])
                price = price_match.group(0) if price_match else "N/A"

                # Find URL near the title
                url_match = re.search(r'href="(/[^"]+)"',
                                      html_content[html_content.find(block) - 200:html_content.find(block)])
                listing_url = "https://www.olx.com.pk" + url_match.group(1) if url_match else ""

                # Find location near the title
                location = "Islamabad"  # Default

                # Extract size from title
                size = "N/A"
                size_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:marla|kanal)', title.lower())
                if size_match:
                    size = size_match.group(0)

                # Create property data - ONLY INCLUDE FIELDS IN THE DATABASE
                property_data = {
                    'title': title,
                    'price': price,
                    'location': location,
                    'description': f"{title}. Located in {location}.",
                    'listing_url': listing_url,
                    'source': 'OLX',
                    'urgency': self._extract_urgency(title),
                    'property_type': 'Plot',
                    'size': size,
                    'seller_name': 'N/A',
                    'contact_number': 'Contact through OLX'
                    # Removed 'email' field
                }

                listings.append(property_data)
                print(f"Found OLX listing from HTML: {title}")

            except Exception as e:
                logger.error(f"Error extracting OLX listing from HTML: {str(e)}")
                continue

        return listings

    def scrape_zameen(self, url):
        """Scrape property listings from Zameen.com"""
        all_listings = []
        html_content = self._get_page(url)

        if not html_content:
            return []

        # Use simple regex approach for Zameen.com since the HTML structure is complex
        # Look for listing blocks by finding property card sections
        print("Processing Zameen.com content...")

        # Extract listing URLs first
        listing_urls = []
        url_matches = re.findall(r'href="(/Property/[^"]+\.html)"', html_content)
        for url_match in url_matches:
            if url_match not in listing_urls:
                listing_urls.append(url_match)

        logger.info(f"Found {len(listing_urls)} Zameen.com listing URLs")
        print(f"Found {len(listing_urls)} Zameen.com listing URLs. Processing details...")

        # Process each listing URL
        for listing_url in listing_urls:
            try:
                full_url = f"https://www.zameen.com{listing_url}" if not listing_url.startswith('http') else listing_url

                # Get the detailed page
                detail_html = self._get_page(full_url)
                if not detail_html:
                    continue

                # Extract title - look for the h1 element
                title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', detail_html)
                title = title_match.group(1).strip() if title_match else "Property in Islamabad"

                # Extract price - look for price class or PKR text
                price = "N/A"
                price_match = re.search(r'PKR\s*[\d,.]+|Rs\.?\s*[\d,.]+|[\d,.]+\s*(?:lac|lakh|crore)', detail_html)
                if price_match:
                    price = price_match.group(0).strip()

                # Extract location
                location = "Islamabad"
                location_match = re.search(r'(?:Address|Location):\s*([^<>]+?)(?:<|,\s*Islamabad)', detail_html)
                if location_match:
                    location = location_match.group(1).strip()

                # Extract size
                size = "N/A"
                size_match = re.search(
                    r'(?:Area|Size):\s*(\d+(?:\.\d+)?\s*(?:Marla|Kanal|Sq\.?\s*(?:Ft|Feet|Yard|Yd)))', detail_html,
                    re.IGNORECASE)
                if size_match:
                    size = size_match.group(1).strip()
                else:
                    # Try to find size in title
                    title_size_match = re.search(r'(\d+(?:\.\d+)?)\s*(?:marla|kanal)', title.lower())
                    if title_size_match:
                        size = title_size_match.group(0)

                # Extract contact info
                contact = "Contact through Zameen.com"
                contact_match = re.search(r'(?:Phone|Mobile|Contact):\s*(03\d{2}[- ]?\d{7}|\+92\d{10})', detail_html)
                if contact_match:
                    contact = contact_match.group(1).strip()

                # Extract description
                description = f"{title}. Located in {location}."
                desc_match = re.search(r'(?:Description|Details):\s*([^<]{20,500})', detail_html)
                if desc_match:
                    description = desc_match.group(1).strip()

                # Check for urgency indicators
                is_hot = "SUPER HOT" in detail_html or "Featured" in detail_html
                urgency = "HIGH" if is_hot else self._extract_urgency(f"{title} {description}")

                # Extract seller name
                seller_name = "N/A"
                seller_match = re.search(r'(?:Agent|Owner|Posted by):\s*([^<]{3,50})', detail_html)
                if seller_match:
                    seller_name = seller_match.group(1).strip()

                # Create property data - ONLY INCLUDE FIELDS IN THE DATABASE
                property_data = {
                    'title': title,
                    'price': price,
                    'location': location,
                    'description': description,
                    'listing_url': full_url,
                    'source': 'Zameen.com',
                    'urgency': urgency,
                    'property_type': 'Plot',
                    'size': size,
                    'seller_name': seller_name,
                    'contact_number': contact
                    # Removed 'email' field
                }

                all_listings.append(property_data)
                print(f"Found Zameen listing: {title}")

            except Exception as e:
                logger.error(f"Error processing Zameen listing: {str(e)}")
                continue

        return all_listings

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
        """Run the direct scraper on specified URLs"""
        total_saved = 0

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
            print(f"{i + 1}. {lead['title']}")
            print(f"   Price: {lead['price']}")
            print(f"   Location: {lead['location']}")
            print(f"   Size: {lead['size'] if 'size' in lead else 'N/A'}")
            print(f"   Contact: {lead['contact_number']}")
            print()

    print("=============================")