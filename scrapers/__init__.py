#!/usr/bin/env python3
# scrapers/__init__.py - Module initialization

# Import all scraper functions for easier access
from scrapers.axis_direct import scrape_axis_direct
from scrapers.icicidirect import scrape_icicidirect 
from scrapers.kotak_securities import scrape_kotak_securities
from scrapers.fivepaisa import scrape_5paisa
from scrapers.sharekhan import scrape_sharekhan
from scrapers.moneycontrol import scrape_moneycontrol

# Define a mapping of website identifiers to their scraper functions
scraper_mapping = {
    "axis_direct": scrape_axis_direct,
    "icici_direct": scrape_icicidirect,
    "kotak_securities": scrape_kotak_securities,
    "fivepaisa": scrape_5paisa,
    "sharekhan": scrape_sharekhan,
    "moneycontrol": scrape_moneycontrol
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
