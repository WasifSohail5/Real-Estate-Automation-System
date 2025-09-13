import random
import requests
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class ProxyHelper:
    """Helper class to manage proxy rotation for scraping"""

    def __init__(self):
        self.proxies = []
        self.current_proxy = None
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.2 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/98.0.4758.102 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/98.0.1108.55"
        ]

    def get_free_proxies(self):
        """Get free proxies from free-proxy-list.net"""
        try:
            url = "https://free-proxy-list.net/"
            response = requests.get(url)
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find the table with proxies
            table = soup.find('table')
            if not table:
                logger.warning("Could not find proxy table")
                return []

            proxies = []
            for row in table.find_all('tr')[1:]:
                cols = row.find_all('td')
                if len(cols) >= 7:
                    ip = cols[0].text.strip()
                    port = cols[1].text.strip()
                    https = cols[6].text.strip()

                    if https == 'yes':  # Only get HTTPS proxies
                        proxy = f"{ip}:{port}"
                        proxies.append(proxy)

            logger.info(f"Found {len(proxies)} free proxies")
            return proxies

        except Exception as e:
            logger.error(f"Error getting free proxies: {e}")
            return []

    def test_proxy(self, proxy, test_url="https://www.google.com", timeout=5):
        """Test if a proxy works"""
        try:
            proxies = {
                "http": f"http://{proxy}",
                "https": f"https://{proxy}"
            }

            response = requests.get(
                test_url,
                proxies=proxies,
                timeout=timeout,
                headers={'User-Agent': random.choice(self.user_agents)}
            )

            return response.status_code == 200
        except:
            return False

    def initialize_proxies(self):
        """Initialize working proxies"""
        if not self.proxies:
            all_proxies = self.get_free_proxies()
            self.proxies = []

            # Test up to 5 proxies to find working ones (to save time)
            test_count = 0
            for proxy in all_proxies:
                if test_count >= 5:
                    break

                test_count += 1
                logger.info(f"Testing proxy: {proxy}")

                if self.test_proxy(proxy):
                    self.proxies.append(proxy)
                    logger.info(f"Found working proxy: {proxy}")

            if not self.proxies:
                logger.warning("No working proxies found")
                # Add a fallback to no proxy
                self.proxies = ["direct"]

        return len(self.proxies) > 0 and self.proxies[0] != "direct"

    def get_proxy_session(self):
        """Get a requests session with proxy rotation"""
        session = requests.Session()

        # Initialize proxies if needed
        if not self.proxies:
            self.initialize_proxies()

        # Choose a random proxy
        if self.proxies and self.proxies[0] != "direct":
            self.current_proxy = random.choice(self.proxies)
            session.proxies = {
                "http": f"http://{self.current_proxy}",
                "https": f"https://{self.current_proxy}"
            }
            logger.info(f"Using proxy: {self.current_proxy}")
        else:
            logger.info("Using direct connection (no proxy)")
            self.current_proxy = None

        # Set a random user agent
        session.headers.update({'User-Agent': random.choice(self.user_agents)})

        return session

    def get_page(self, url, timeout=10, retries=3):
        """Get a page with proxy rotation and retry logic"""
        for i in range(retries):
            try:
                session = self.get_proxy_session()
                response = session.get(url, timeout=timeout)

                if response.status_code == 200:
                    return response.text
                else:
                    logger.warning(f"Failed to get {url}: Status {response.status_code}")

                    # If forbidden or rate limited, try a different proxy
                    if response.status_code in [403, 429, 503]:
                        if self.current_proxy in self.proxies:
                            self.proxies.remove(self.current_proxy)
                        continue
            except Exception as e:
                logger.error(f"Error getting {url}: {e}")

                # Remove failed proxy
                if self.current_proxy in self.proxies:
                    self.proxies.remove(self.current_proxy)

        return None