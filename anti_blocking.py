#!/usr/bin/env python3
# anti_blocking.py - Anti-blocking mechanisms for web scraping

import random
import time
import requests
from requests.exceptions import RequestException
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AntiBlockingManager:
    """
    Manages anti-blocking techniques for web scraping.
    - Rotates user agents
    - Implements random delays
    - Handles retries with exponential backoff
    - Provides site-specific configurations
    """
    
    def __init__(self, use_rotating_agents=True, use_random_delays=True):
        self.use_rotating_agents = use_rotating_agents
        self.use_random_delays = use_random_delays
        
        # List of user agents to rotate
        self.user_agents = [
            # Desktop browsers
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/112.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 13_3_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 Edg/112.0.1722.58',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 OPR/96.0.4693.50',
            # Mobile browsers
            'Mozilla/5.0 (iPhone; CPU iPhone OS 16_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Android 13; Mobile; rv:109.0) Gecko/113.0 Firefox/113.0',
            'Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Mobile Safari/537.36',
            'Mozilla/5.0 (iPad; CPU OS 16_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.4 Mobile/15E148 Safari/604.1',
        ]
        
        # Site-specific configurations
        self.site_configs = {
            'economictimes.indiatimes.com': {
                'headers': {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Referer': 'https://economictimes.indiatimes.com/',
                    'DNT': '1',
                },
                'min_delay': 2,
                'max_delay': 5,
            },
            'moneycontrol.com': {
                'headers': {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Referer': 'https://www.google.com/',
                    'DNT': '1',
                    'sec-ch-ua': '"Google Chrome";v="112", "Not:A-Brand";v="99", "Chromium";v="112"',
                    'sec-ch-ua-mobile': '?0',
                    'sec-ch-ua-platform': '"macOS"',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Upgrade-Insecure-Requests': '1',
                    'Cache-Control': 'max-age=0',
                },
                'min_delay': 4,
                'max_delay': 7,
                'retries': 5,  # Higher number of retries
                'special_handling': True,  # Flag for sites needing special handling
            },
            'livemint.com': {
                'headers': {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Referer': 'https://www.livemint.com/',
                    'DNT': '1',
                },
                'min_delay': 2,
                'max_delay': 4,
            },
            '5paisa.com': {
                'headers': {
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Referer': 'https://www.5paisa.com/',
                    'DNT': '1',
                },
                'min_delay': 3,
                'max_delay': 5,
            },
        }
        
        # Default configuration for sites not in site_configs
        self.default_config = {
            'headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'DNT': '1',
            },
            'min_delay': 1,
            'max_delay': 3,
            'retries': 2,
            'special_handling': False,
        }
        
        # Session to maintain cookies
        self.session = requests.Session()
    
    def _get_random_user_agent(self):
        """Get a random user agent from the list"""
        return random.choice(self.user_agents)
    
    def _get_site_config(self, url):
        """Get the configuration for a specific site or default if not found"""
        for domain, config in self.site_configs.items():
            if domain in url:
                # Merge with default config to ensure all keys exist
                merged_config = self.default_config.copy()
                merged_config.update(config)
                return merged_config
        return self.default_config
    
    def _apply_delay(self, config):
        """Apply a random delay between min and max based on configuration"""
        if self.use_random_delays:
            delay = random.uniform(config['min_delay'], config['max_delay'])
            logger.debug(f"Applying delay of {delay:.2f} seconds")
            time.sleep(delay)
    
    def _handle_special_site(self, url, headers, config):
        """Apply special handling for sites with strict anti-bot measures"""
        if 'moneycontrol.com' in url:
            # For MoneyControl, fetch the homepage first to establish cookies
            try:
                logger.debug("Applying special handling for MoneyControl")
                home_url = "https://www.moneycontrol.com/"
                # Add a random UTM parameter to avoid caching
                rand_param = f"?utm_source=scraper&utm_medium=test&r={random.randint(1000, 9999)}"
                
                # Fetch the homepage with a different referer
                headers['Referer'] = 'https://www.google.com/search?q=moneycontrol+india+stock+news'
                
                # For User-Agent, pick one and stick with it (rotating might trigger defenses)
                if 'User-Agent' not in headers:
                    headers['User-Agent'] = self.user_agents[0]  # Use first one consistently
                
                # First visit simulates a Google search landing
                logger.debug("Establishing session with homepage visit")
                self.session.get(
                    home_url + rand_param,
                    headers=headers,
                    timeout=30
                )
                
                # Wait before next request
                time.sleep(random.uniform(1, 3))
                
                # Now change referer to internal page
                headers['Referer'] = home_url
                return headers
            except Exception as e:
                logger.warning(f"Error in special handling for MoneyControl: {e}")
        
        return headers  # Return unchanged headers for non-special sites
    
    def fetch_with_anti_blocking(self, url, retries=None, timeout=30):
        """
        Fetch content from a URL with anti-blocking techniques.
        
        Args:
            url (str): The URL to fetch
            retries (int): Number of retries on failure
            timeout (int): Request timeout in seconds
            
        Returns:
            tuple: (success, content, status_code)
                - success (bool): True if fetch was successful
                - content (str or None): The page content if successful, error message if not
                - status_code (int or None): HTTP status code if available
        """
        config = self._get_site_config(url)
        headers = config['headers'].copy()
        
        # Use specified retries or from config or default
        retries_count = retries if retries is not None else config.get('retries', self.default_config['retries'])
        
        if self.use_rotating_agents:
            headers['User-Agent'] = self._get_random_user_agent()
        
        # Apply special handling for sites with strict anti-bot measures
        if config.get('special_handling', False):
            headers = self._handle_special_site(url, headers, config)
        
        self._apply_delay(config)
        
        attempt = 0
        while attempt < retries_count:
            try:
                logger.debug(f"Fetching {url} (Attempt {attempt+1}/{retries_count})")
                
                # Add cache-busting parameter
                cache_buster = f"{'&' if '?' in url else '?'}_cb={int(time.time())}" if attempt > 0 else ""
                request_url = url + cache_buster
                
                response = self.session.get(
                    request_url,
                    headers=headers,
                    timeout=timeout,
                    allow_redirects=True,  # Follow redirects
                )
                
                # Check for common anti-bot responses
                if response.status_code == 200:
                    # Check if we got a CAPTCHA or a bot detection page (common responses are small)
                    if len(response.text) < 500 and ('captcha' in response.text.lower() or 'robot' in response.text.lower()):
                        logger.warning(f"Possible bot detection (small page with CAPTCHA/robot text) for {url}")
                        wait_time = (2 ** attempt) * random.uniform(2, 4)
                        time.sleep(wait_time)
                        attempt += 1
                        continue
                    
                    return True, response.text, response.status_code
                elif response.status_code == 403 or response.status_code == 429:
                    # Forbidden or Too Many Requests - increase delay for next attempt
                    logger.warning(f"Received {response.status_code} from {url}. Increasing delay.")
                    wait_time = (2 ** attempt) * random.uniform(2, 5)
                    time.sleep(wait_time)
                else:
                    logger.warning(f"Received {response.status_code} from {url}")
                    return False, f"HTTP Error: {response.status_code}", response.status_code
            
            except RequestException as e:
                logger.warning(f"Request error for {url}: {str(e)}")
                if attempt == retries_count - 1:  # Last attempt
                    return False, f"Request Error: {str(e)}", None
            
            attempt += 1
            # Apply exponential backoff
            backoff_time = (2 ** attempt) * random.uniform(1, 3)
            logger.debug(f"Retrying in {backoff_time:.2f} seconds")
            time.sleep(backoff_time)
        
        return False, "Max retries exceeded", None