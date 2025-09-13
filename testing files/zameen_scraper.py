import requests
import time
import logging
from bs4 import BeautifulSoup
from scraper_base import BaseScraper, logger
from proxy_helper import ProxyHelper


class ZameenScraper(BaseScraper):
    """Scraper for Zameen.com real estate listings"""

    def __init__(self):
        super().__init__("https://www.zameen.com")
        self.proxy_helper = ProxyHelper()

    def extract_property_listings(self, location="islamabad", num_pages=2, purpose="buy"):
        """Extract property listings from Zameen.com"""
        all_listings = []

        # Updated URL patterns for Zameen.com (as of September 2025)
        url_patterns = [
            # Format: city/property-type
            f"{self.base_url}/Homes/{location}/",
            f"{self.base_url}/Plots/{location}/",
            f"{self.base_url}/Commercial/{location}/",
            # Alternative format with search query
            f"{self.base_url}/search/results.php?category=1&city={location}&q={location}"
        ]

        for url_pattern in url_patterns:
            if len(all_listings) > 20:  # If we've found enough listings, stop
                break

            logger.info(f"Trying URL pattern: {url_pattern}")

            for page in range(1, num_pages + 1):
                try:
                    # Add page number to URL if not first page
                    if page > 1:
                        if "?" in url_pattern:
                            url = f"{url_pattern}&page={page}"
                        else:
                            url = f"{url_pattern}?page={page}"
                    else:
                        url = url_pattern

                    logger.info(f"Scraping page {page} from Zameen: {url}")

                    # Use proxy helper to get around blocking
                    html_content = self.proxy_helper.get_page(url)

                    if not html_content:
                        logger.warning(f"Failed to get content from {url}")
                        continue

                    soup = self._parse_html(html_content)

                    # Try multiple property card selectors
                    property_cards = []
                    selectors_to_try = [
                        'article.listingCard',
                        'li[role="article"]',
                        '.ef447dde',
                        'div[data-testid="listing-card"]',
                        'div.listingCard',
                        'div.property-list-item'
                    ]

                    for selector in selectors_to_try:
                        property_cards = soup.select(selector)
                        if property_cards:
                            logger.info(f"Found {len(property_cards)} property cards using selector: {selector}")
                            break

                    if not property_cards:
                        logger.warning(f"No property cards found on page {page}")
                        continue

                    # Process each property card
                    for card in property_cards:
                        try:
                            # Extract title
                            title_elem = None
                            for title_selector in ['h2', '.c21a3f5e', 'h2.listingTile__title', '.property-title']:
                                title_elem = card.select_one(title_selector)
                                if title_elem:
                                    break

                            if not title_elem:
                                continue

                            title = title_elem.text.strip()

                            # Extract price
                            price = 'N/A'
                            price_selectors = ['.d6e81fd0', '.property-price', 'span.price']
                            for selector in price_selectors:
                                price_elem = card.select_one(selector)
                                if price_elem:
                                    price = price_elem.text.strip()
                                    break

                            # Extract location
                            property_location = 'N/A'
                            location_selectors = ['._162e6469', '.property-location', '.listingTile__address']
                            for selector in location_selectors:
                                location_elem = card.select_one(selector)
                                if location_elem:
                                    property_location = location_elem.text.strip()
                                    break

                            # Extract link
                            listing_url = ''
                            link_elem = card.select_one('a[href]')
                            if link_elem:
                                listing_url = link_elem['href']
                                if not listing_url.startswith('http'):
                                    listing_url = self.base_url + listing_url

                            # Extract description (if available)
                            description = ''
                            description_selectors = ['._7ac32433', '.listingTile__description', '.property-description']
                            for selector in description_selectors:
                                desc_elem = card.select_one(selector)
                                if desc_elem:
                                    description = desc_elem.text.strip()
                                    break

                            # Extract property type from URL or card
                            property_type = 'Unknown'
                            if 'home' in url_pattern.lower() or 'home' in listing_url.lower():
                                property_type = 'Home'
                            elif 'plot' in url_pattern.lower() or 'plot' in listing_url.lower():
                                property_type = 'Plot'
                            elif 'commercial' in url_pattern.lower() or 'commercial' in listing_url.lower():
                                property_type = 'Commercial'

                            # Determine urgency
                            urgency = self._extract_urgency(f"{title} {description}")

                            property_data = {
                                'title': title,
                                'price': price,
                                'location': property_location,
                                'description': description,
                                'listing_url': listing_url,
                                'source': 'Zameen.com',
                                'urgency': urgency,
                                'property_type': property_type
                            }

                            all_listings.append(property_data)
                            logger.info(f"Extracted listing: {title}")

                        except Exception as e:
                            logger.error(f"Error extracting property card: {e}")
                            continue

                    # Sleep to avoid rate limiting
                    time.sleep(random.uniform(2, 5))

                except Exception as e:
                    logger.error(f"Error processing page {page}: {e}")
                    continue

        num_listings = len(all_listings)
        logger.info(f"Total listings extracted from Zameen.com: {num_listings}")
        return all_listings

    def extract_listing_details(self, listing_url):
        """Extract detailed information about a specific Zameen.com property listing"""
        try:
            logger.info(f"Extracting details from: {listing_url}")

            # Use proxy helper to get around blocking
            html_content = self.proxy_helper.get_page(listing_url)

            if not html_content:
                logger.warning(f"Failed to get content from {listing_url}")
                return None

            soup = self._parse_html(html_content)

            # Extract basic property details
            title = 'N/A'
            price = 'N/A'
            location = 'N/A'
            description = ''
            property_size = 'N/A'
            bedrooms = 0
            bathrooms = 0
            property_type = 'N/A'

            # Extract title
            title_selectors = ['h1', '.c0df3811', '.property-title']
            for selector in title_selectors:
                elem = soup.select_one(selector)
                if elem:
                    title = elem.text.strip()
                    break

            # Extract price
            price_selectors = ['.c4fc20ba', '.property-price', '.fa2044a3']
            for selector in price_selectors:
                elem = soup.select_one(selector)
                if elem:
                    price = elem.text.strip()
                    break

            # Extract location
            location_selectors = ['._1a682f13', '.property-location', '.ccd005d3']
            for selector in location_selectors:
                elem = soup.select_one(selector)
                if elem:
                    location = elem.text.strip()
                    break

            # Extract description
            description_selectors = ['._96aa05ec', '.property-description', '.b1234deb']
            for selector in description_selectors:
                elem = soup.select_one(selector)
                if elem:
                    description = elem.text.strip()
                    break

            # Extract property features
            # Try to find feature icons or specs table
            feature_selectors = ['._17984a2c', '.property-details', '.ed429e12']
            for selector in feature_selectors:
                features = soup.select(selector)
                for feature in features:
                    text = feature.text.lower()

                    if 'bed' in text:
                        match = re.search(r'(\d+)\s*bed', text)
                        if match:
                            bedrooms = int(match.group(1))

                    elif 'bath' in text:
                        match = re.search(r'(\d+)\s*bath', text)
                        if match:
                            bathrooms = int(match.group(1))

                    elif any(size_unit in text for size_unit in ['marla', 'kanal', 'sq ft', 'sqft']):
                        property_size = text.strip()

            # Determine property type
            if 'house' in title.lower() or 'home' in title.lower():
                property_type = 'House'
            elif 'plot' in title.lower() or 'land' in title.lower():
                property_type = 'Plot'
            elif 'apartment' in title.lower() or 'flat' in title.lower():
                property_type = 'Apartment'
            elif any(commercial in title.lower() for commercial in ['shop', 'office', 'commercial', 'plaza']):
                property_type = 'Commercial'

            # Get seller info
            seller_name = 'N/A'
            seller_selectors = ['._5a89a970', '.agent-name', '.f8b89d75']
            for selector in seller_selectors:
                elem = soup.select_one(selector)
                if elem:
                    seller_name = elem.text.strip()
                    break

            # Determine urgency
            urgency = self._extract_urgency(f"{title} {description}")

            property_details = {
                'title': title,
                'description': description,
                'price': price,
                'location': location,
                'property_type': property_type,
                'size': property_size,
                'bedrooms': bedrooms,
                'bathrooms': bathrooms,
                'seller_name': seller_name,
                'contact_number': 'Click to show on Zameen.com',
                'listing_url': listing_url,
                'source': 'Zameen.com',
                'urgency': urgency
            }

            logger.info(f"Extracted details for: {title}")
            return property_details

        except Exception as e:
            logger.error(f"Error extracting listing details: {e}")
            return None