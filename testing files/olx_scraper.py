import re
import logging
import requests
import time
import random
from bs4 import BeautifulSoup
from scraper_base import BaseScraper, logger


class OlxScraper(BaseScraper):
    """Updated scraper for OLX Pakistan real estate listings based on current URL structure"""

    def __init__(self):
        super().__init__("https://www.olx.com.pk")
        # OLX location codes (can be expanded)
        self.location_codes = {
            "islamabad": "g4060615",
            "lahore": "g4060459",
            "karachi": "g4060449",
            "rawalpindi": "g4060716"
        }
        # OLX property category codes
        self.category_codes = {
            "land_plots": "c40",
            "houses": "c4969",
            "apartments": "c4970",
            "shops": "c4972",
            "offices": "c4971"
        }

    def get_url_for_location_category(self, location, category):
        """Generate proper OLX URL based on location and category"""
        location_lower = location.lower()

        # Get location code or use location name if code not found
        loc_code = ""
        if location_lower in self.location_codes:
            loc_code = f"_{self.location_codes[location_lower]}"

        # Get category code or use default if not found
        cat_code = ""
        if category in self.category_codes:
            cat_code = f"_{self.category_codes[category]}"

        # Form the URL
        url = f"{self.base_url}/{location_lower}{loc_code}"
        if cat_code:
            url += f"/{category}{cat_code}"

        return url

    def extract_property_listings(self, location="islamabad", category="land_plots", num_pages=2):
        """Extract property listings from OLX using current URL structure"""
        all_listings = []

        # Get the base URL for this location and category
        base_url = self.get_url_for_location_category(location, category)
        logger.info(f"Using base URL: {base_url}")

        for page in range(1, num_pages + 1):
            try:
                # Add page parameter for pagination
                url = f"{base_url}?page={page}" if page > 1 else base_url
                logger.info(f"Scraping page {page} from OLX: {url}")

                # Enhanced headers to avoid detection
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.5",
                    "Referer": "https://www.olx.com.pk/",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                    "Cache-Control": "max-age=0"
                }

                # Add delay to avoid being detected as a bot
                time.sleep(random.uniform(1, 3))

                response = requests.get(url, headers=headers, timeout=15)

                if response.status_code != 200:
                    logger.warning(f"Failed to load page: Status {response.status_code}")
                    continue

                html_content = response.text
                soup = self._parse_html(html_content)

                # Based on your screenshot, find listing cards
                # Try multiple possible selectors for listings
                listings = []
                selectors_to_try = [
                    'li[data-cy="l-card"]',  # Common listing card selector
                    'div[data-testid="listing-card"]',
                    'div.css-19ucd76',  # Possible class name
                    'li.ListItem_listItem__ZMIh6',  # Another possible class
                    'a._2_U0U'  # Link to listing
                ]

                for selector in selectors_to_try:
                    listings = soup.select(selector)
                    if listings:
                        logger.info(f"Found {len(listings)} listings using selector: {selector}")
                        break

                if not listings:
                    logger.warning(f"No listings found on page {page}")
                    continue

                # Process each listing
                for listing in listings:
                    try:
                        # Get the listing link
                        link_elem = listing.select_one('a[href]') or listing
                        if not link_elem or not link_elem.has_attr('href'):
                            continue

                        listing_url = link_elem['href']
                        if not listing_url.startswith('http'):
                            listing_url = self.base_url + listing_url

                        # Get title
                        title = None
                        title_selectors = ['h2', '.css-1q7gvpp', '.css-16v5mdi', '[data-testid="ad-title"]']
                        for selector in title_selectors:
                            title_elem = listing.select_one(selector)
                            if title_elem:
                                title = title_elem.text.strip()
                                break

                        if not title:
                            continue

                        # Get price
                        price = 'N/A'
                        price_selectors = ['.css-10b0gli', '.css-1q7gvpp', '[data-testid="ad-price"]']
                        for selector in price_selectors:
                            price_elem = listing.select_one(selector)
                            if price_elem:
                                price = price_elem.text.strip()
                                break

                        # Get location
                        location_text = 'N/A'
                        location_selectors = ['.css-7l2d93', '.css-1kqeevq', '[data-testid="ad-location"]']
                        for selector in location_selectors:
                            location_elem = listing.select_one(selector)
                            if location_elem:
                                location_text = location_elem.text.strip()
                                break

                        # Get description (if available)
                        description = ''
                        desc_selectors = ['.css-lsymcb', '.css-1kqeevq', '[data-testid="ad-description"]']
                        for selector in desc_selectors:
                            desc_elem = listing.select_one(selector)
                            if desc_elem:
                                description = desc_elem.text.strip()
                                break

                        # Determine property type from category and title
                        property_type = category.replace('_', ' ').title()

                        # Extract property size from title or description
                        size_match = re.search(r'(\d+)\s*(marla|kanal|sq\.?\s*ft|square\s*feet|sq\.?\s*yd)',
                                               f"{title} {description}".lower())
                        size = size_match.group() if size_match else "N/A"

                        # Determine urgency
                        urgency = self._extract_urgency(f"{title} {description}")

                        # Create listing data
                        property_data = {
                            'title': title,
                            'price': price,
                            'location': location_text,
                            'description': description,
                            'listing_url': listing_url,
                            'source': 'OLX',
                            'urgency': urgency,
                            'property_type': property_type,
                            'size': size
                        }

                        all_listings.append(property_data)
                        logger.info(f"Extracted listing: {title}")

                    except Exception as e:
                        logger.error(f"Error extracting listing: {e}")
                        continue

            except Exception as e:
                logger.error(f"Error processing page {page}: {e}")
                continue

        num_listings = len(all_listings)
        logger.info(f"Total OLX listings extracted: {num_listings}")
        return all_listings

    def extract_listing_details(self, listing_url):
        """Extract detailed information from a specific OLX listing"""
        try:
            if not listing_url or 'olx.com.pk' not in listing_url:
                return None

            logger.info(f"Extracting details from: {listing_url}")

            # Enhanced headers
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Referer": "https://www.olx.com.pk/",
            }

            # Add delay to avoid being detected as a bot
            time.sleep(random.uniform(2, 4))

            response = requests.get(listing_url, headers=headers, timeout=15)

            if response.status_code != 200:
                logger.warning(f"Failed to load listing: Status {response.status_code}")
                return None

            html_content = response.text
            soup = self._parse_html(html_content)

            # Extract basic details
            title = 'N/A'
            price = 'N/A'
            description = ''
            location = 'N/A'
            seller_name = 'N/A'
            property_size = 'N/A'
            property_type = 'N/A'

            # Title
            title_selectors = ['h1', '.css-1q7gvpp', '[data-testid="ad-title"]', '.css-1soizd2']
            for selector in title_selectors:
                elem = soup.select_one(selector)
                if elem:
                    title = elem.text.strip()
                    break

            # Price
            price_selectors = ['.css-10b0gli', '.css-1q7gvpp', '[data-testid="ad-price"]']
            for selector in price_selectors:
                elem = soup.select_one(selector)
                if elem:
                    price = elem.text.strip()
                    break

            # Description
            desc_selectors = ['.css-g5mtbi-Text', '[data-testid="description-text"]', '.css-1d7g5qg']
            for selector in desc_selectors:
                elem = soup.select_one(selector)
                if elem:
                    description = elem.text.strip()
                    break

            # Location
            location_selectors = ['.css-1cju8pu', '[data-testid="location-date"]', '.css-1avehqx']
            for selector in location_selectors:
                elem = soup.select_one(selector)
                if elem:
                    location = elem.text.strip()
                    break

            # Extract property details from description using regex
            if description:
                # Try to extract size
                size_match = re.search(r'(\d+)\s*(marla|kanal|sq\.?\s*ft|square\s*feet|sq\.?\s*yd)',
                                       description.lower())
                if size_match:
                    property_size = size_match.group()

                # Try to determine property type
                property_types = ['plot', 'land', 'house', 'apartment', 'flat', 'commercial', 'shop', 'office']
                for p_type in property_types:
                    if p_type in title.lower() or p_type in description.lower():
                        property_type = p_type.capitalize()
                        break

            # Get seller info
            seller_selectors = ['.css-1rn0irl', '[data-testid="seller-name"]']
            for selector in seller_selectors:
                elem = soup.select_one(selector)
                if elem:
                    seller_name = elem.text.strip()
                    break

            # Try to find contact number (usually hidden or requires clicking)
            contact_number = 'Contact through OLX'

            # Extract parameters from detail table
            params = {}
            param_rows = soup.select('.css-1qo3kgc tr') or soup.select('[data-testid="ad-details"] tr')
            for row in param_rows:
                cells = row.select('td')
                if len(cells) >= 2:
                    key = cells[0].text.strip()
                    value = cells[1].text.strip()
                    params[key.lower()] = value

                    # Update property size if we find it
                    if 'area' in key.lower() or 'size' in key.lower():
                        property_size = value

            # Determine urgency
            urgency = self._extract_urgency(f"{title} {description}")

            # Create detailed property data
            property_details = {
                'title': title,
                'description': description,
                'price': price,
                'location': location,
                'property_type': property_type,
                'size': property_size,
                'seller_name': seller_name,
                'contact_number': contact_number,
                'listing_url': listing_url,
                'source': 'OLX',
                'urgency': urgency,
                'parameters': params
            }

            logger.info(f"Extracted details for: {title}")
            return property_details

        except Exception as e:
            logger.error(f"Error extracting listing details: {e}")
            return None