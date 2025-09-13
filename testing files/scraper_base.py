from abc import ABC, abstractmethod
import requests
from bs4 import BeautifulSoup
import time
import random
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler('scraper.log'), logging.StreamHandler()]
)
logger = logging.getLogger('real_estate_scraper')


class BaseScraper(ABC):
    """Base class for all property website scrapers"""

    def __init__(self, base_url, headers=None):
        self.base_url = base_url
        self.headers = headers or {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        self.session = requests.Session()

    def _get_page(self, url):
        """Fetch page content with error handling and rate limiting"""
        try:
            # Add small random delay to avoid being blocked
            time.sleep(random.uniform(1, 3))

            logger.info(f"Fetching URL: {url}")
            response = self.session.get(url, headers=self.headers)
            response.raise_for_status()

            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching URL {url}: {e}")
            return None

    def _parse_html(self, html_content):
        """Parse HTML content into BeautifulSoup object"""
        if html_content:
            return BeautifulSoup(html_content, 'html.parser')
        return None

    def _extract_urgency(self, text):
        """Extract urgency level from listing text"""
        if not text:
            return "NORMAL"

        text = text.lower()
        high_urgency_keywords = [
            "urgent", "urgently", "immediate", "quick sale", "quick deal",
            "fast sale", "hurry", "asap", "bargain", "distress", "must sell",
            "leaving city", "leaving country"
        ]

        medium_urgency_keywords = [
            "good deal", "great deal", "negotiable", "price reduced",
            "below market", "motivated", "open to offers"
        ]

        if any(keyword in text for keyword in high_urgency_keywords):
            return "HIGH"
        elif any(keyword in text for keyword in medium_urgency_keywords):
            return "MEDIUM"
        else:
            return "NORMAL"

    @abstractmethod
    def extract_property_listings(self, location, num_pages=2):
        """
        Extract property listings for the given location

        Args:
            location (str): Location to search for properties
            num_pages (int): Number of pages to scrape

        Returns:
            list: List of property dictionaries
        """
        pass

    @abstractmethod
    def extract_listing_details(self, listing_url):
        """
        Extract detailed information about a specific property listing

        Args:
            listing_url (str): URL of the property listing

        Returns:
            dict: Property details dictionary
        """
        pass