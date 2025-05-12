#!/usr/bin/env python3
# scrapers/__init__.py - Module initialization for target website scrapers

# Import all target website scrapers
from scrapers.axis_direct import scrape_axis_direct
from scrapers.icici_direct import scrape_icici_direct
from scrapers.fivepaisa import scrape_5paisa
from scrapers.moneycontrol import scrape_moneycontrol

# Define a mapping of website identifiers to their scraper functions
scraper_mapping = {
    "axis_direct": scrape_axis_direct,
    "icici_direct": scrape_icici_direct,
    "5paisa": scrape_5paisa,
    "moneycontrol": scrape_moneycontrol
}

# Define URLs for each target website
target_urls = {
    "axis_direct": "https://simplehai.axisdirect.in/research/research-ideas/trade-ideas",
    "icici_direct": "https://www.icicidirect.com/research/equity/investing-ideas",
    "5paisa": "https://www.5paisa.com/share-market-today/stocks-to-buy-or-sell-today",
    "moneycontrol": "https://www.moneycontrol.com/markets/stock-ideas/"
}

# Function to get the appropriate scraper function
def get_scraper(source_name):
    """
    Get the appropriate scraper function for a given source name
    
    Args:
        source_name (str): Identifier for the source/website
        
    Returns:
        function: The corresponding scraper function or None if not found
    """
    return scraper_mapping.get(source_name)

# Function to get URL for a source
def get_url(source_name):
    """
    Get the URL for a given source name
    
    Args:
        source_name (str): Identifier for the source/website
        
    Returns:
        str: The corresponding URL or None if not found
    """
    return target_urls.get(source_name)

# List of all target sources
TARGET_SOURCES = list(target_urls.keys())
