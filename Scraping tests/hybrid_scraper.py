import requests
import re
import time
import random
import logging
from bs4 import BeautifulSoup
from database_operations import DatabaseManager

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('scraper.log'), logging.StreamHandler()]
)
logger = logging.getLogger('hybrid_scraper')

class HybridScraper:
    """Hybrid scraper using HTTP requests with occasional Selenium assistance"""
    
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
    
    def _get_page(self, url, max_retries=3):
        """Get webpage content with retries"""
        for attempt in range(max_retries):
            try:
                # Add small random delay to avoid being detected as a bot
                time.sleep(random.uniform(1, 3))
                
                print(f"Attempt {attempt+1} - Fetching URL: {url}")
                response = self.session.get(url, timeout=15)
                
                if response.status_code == 200:
                    print(f"Successfully loaded page ({len(response.text)} bytes)")
                    return response.text
                else:
                    print(f"Failed to load page: Status code {response.status_code}")
            except Exception as e:
                print(f"Error fetching URL (attempt {attempt+1}): {str(e)}")
            
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
    
    def scrape_olx(self, url):
        """Scrape property listings from OLX"""
        all_listings = []
        html_content = self._get_page(url)
        
        if not html_content:
            return []
            
        print("Processing OLX page content...")
        
        # Try to extract listings with BeautifulSoup
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
                # Find a parent that contains both the title and a price
                parent = elem
                for _ in range(5):  # Go up to 5 levels
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
                    block = block_match[0]  # Get the matching HTML block
                    
                    try:
                        # Extract title
                        title_match = re.search(r'<h2[^>]*>([^<]+)</h2>', block)
                        if not title_match:
                            continue
                        
                        title = title_match.group(1).strip()
                        
                        # Extract price
                        price_match = re.search(r'(?:Rs|PKR)[^\d]*(\d[\d,]*)', block)
                        price = f"Rs {price_match.group(1)}" if price_match else "N/A"
                        
                        # Extract link
                        url_match = re.search(r'href="([^"]+)"', block)
                        listing_url = url_match.group(1) if url_match else ""
                        if listing_url and not listing_url.startswith('http'):
                            listing_url = f"https://www.olx.com.pk{listing_url}"
                        
                        # Extract size from title
                        size = self._extract_size_from_text(title)
                        
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
                            'seller_name': 'N/A',
                            'contact_number': 'Contact through OLX'
                        }
                        
                        all_listings.append(property_data)
                        print(f"Extracted OLX listing: {title}")
                    except Exception as e:
                        print(f"Error extracting OLX listing: {str(e)}")
        
        # Process found elements with BeautifulSoup
        for element in listing_elements:
            try:
                # Extract title
                title_elem = element.select_one('h2, span.fTZT3, span._2Vp0i')
                if not title_elem:
                    continue
                
                title = title_elem.text.strip()
                
                # Extract price
                price = "N/A"
                price_elems = element.select('span')
                for elem in price_elems:
                    if 'Rs' in elem.text or 'PKR' in elem.text:
                        price = elem.text.strip()
                        break
                
                # Extract URL
                link_elem = element.select_one('a[href]')
                listing_url = link_elem['href'] if link_elem else ""
                if listing_url and not listing_url.startswith('http'):
                    listing_url = f"https://www.olx.com.pk{listing_url}"
                
                # Extract size from title
                size = self._extract_size_from_text(title)
                
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
                    'seller_name': 'N/A',
                    'contact_number': 'Contact through OLX'
                }
                
                all_listings.append(property_data)
                print(f"Extracted OLX listing: {title}")
            except Exception as e:
                print(f"Error processing OLX element: {str(e)}")
        
        print(f"Successfully extracted {len(all_listings)} listings from OLX")
        return all_listings
    
    def scrape_zameen(self, url):
        """Scrape property listings from Zameen.com"""
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
        
        # Process each listing URL to get details
        for listing_url in listing_urls:
            try:
                full_url = f"https://www.zameen.com{listing_url}"
                
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
                
                # Extract property details
                size = "N/A"
                
                # Try to extract size from property specs
                spec_elems = listing_soup.select('li._17984a2c, div.fe2e5c5d')
                for elem in spec_elems:
                    text = elem.text.lower()
                    if 'area' in text or 'marla' in text or 'kanal' in text:
                        size = elem.text.strip()
                        break
                
                # If size not found in specs, try to extract from title or description
                if size == "N/A":
                    size = self._extract_size_from_text(f"{title} {description}")
                
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
                    'seller_name': 'N/A',
                    'contact_number': 'Contact through Zameen.com'
                }
                
                all_listings.append(property_data)
                print(f"Extracted Zameen.com listing: {title}")
                
                # Add a small delay to avoid overloading the server
                time.sleep(random.uniform(1, 2))
                
            except Exception as e:
                print(f"Error processing Zameen.com listing: {str(e)}")
        
        # If we couldn't extract listings from individual pages, try extracting from the main page
        if not all_listings:
            print("Trying to extract listings directly from Zameen.com main page...")
            
            # Parse the HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Try to find property cards
            cards = soup.select('li[role="article"], article.listingCard, div._357a9937')
            print(f"Found {len(cards)} Zameen.com listing cards")
            
            for card in cards:
                try:
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
                    link_elem = card.select_one('a[href]')
                    listing_url = link_elem['href'] if link_elem else ""
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
                        'seller_name': 'N/A',
                        'contact_number': 'Contact through Zameen.com'
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
        """Run the hybrid scraper on specified URLs"""
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
    print("===== Hybrid Real Estate Scraper =====")
    print("Scraping with HTTP requests and regex pattern matching...")
    
    # Direct URLs to scrape
    olx_url = "https://www.olx.com.pk/islamabad_g4060615/land-plots_c40"
    zameen_url = "https://www.zameen.com/Plots/Islamabad-3-1.html"
    
    # Create the hybrid scraper
    scraper = HybridScraper()
    
    results = scraper.run(olx_url, zameen_url)
    
    print("\n===== Scraping Results =====")
    print(f"OLX Listings found: {results['olx_count']}")
    print(f"Zameen Listings found: {results['zameen_count']}")
    print(f"Total listings saved to database: {results['total_saved']}")
    print(f"Urgent leads found: {results['urgent_count']}")
    
    # Display some urgent leads if available
    if results['urgent_count'] > 0:
        print("\n===== Top Urgent Leads =====")
        for i, lead in enumerate(results['urgent_leads'][:5]):
            print(f"{i+1}. {lead['title']}")
            print(f"   Price: {lead['price']}")
            print(f"   Location: {lead['location']}")
            print(f"   Size: {lead['size'] if 'size' in lead else 'N/A'}")
            print(f"   Contact: {lead['contact_number']}")
            print()
    
    print("=============================")