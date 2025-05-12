#!/usr/bin/env python3
# test_all_scrapers.py - Test all working scrapers in the project

import os
import json
import logging
from datetime import datetime
from bs4 import BeautifulSoup

# Import core modules
from base_scraper import fetch_content_with_ab
from data_processing import deduplicate_stock_tips

# Import scrapers
from scrapers import TARGET_SOURCES, get_url

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
)
logger = logging.getLogger(__name__)

def test_scraper(source_name):
    """
    Test a specific scraper
    
    Args:
        source_name (str): Name of the scraper source
        
    Returns:
        list: Stock tips extracted by the scraper
    """
    # Import the scraper dynamically
    if source_name == "axis_direct":
        from scrapers.axis_direct import scrape_axis_direct as scraper_func
    elif source_name == "icici_direct":
        from scrapers.icici_direct import scrape_icici_direct as scraper_func
    elif source_name == "5paisa":
        from scrapers.fivepaisa import scrape_5paisa as scraper_func
    elif source_name == "moneycontrol":
        from scrapers.moneycontrol import scrape_moneycontrol as scraper_func
    else:
        logger.error(f"Unknown scraper source: {source_name}")
        return []
    
    # Get the URL for this source
    url = get_url(source_name)
    if not url:
        logger.error(f"No URL found for {source_name}")
        return []
    
    logger.info(f"Testing {source_name} scraper for URL: {url}")
    
    # Fetch content
    html_content = fetch_content_with_ab(url)
    if not html_content:
        logger.error(f"Failed to fetch content from {url}")
        return []
    
    # Parse HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Run the scraper
    logger.info(f"Running {source_name} scraper...")
    try:
        stock_tips = scraper_func(soup, url)
        logger.info(f"Found {len(stock_tips)} stock tips from {source_name}")
        return stock_tips
    except Exception as e:
        logger.error(f"Error running {source_name} scraper: {e}", exc_info=True)
        return []

def save_test_results(stock_tips, source_name):
    """
    Save scraper test results to JSON file
    
    Args:
        stock_tips (list): Stock tips to save
        source_name (str): Source name for filename
        
    Returns:
        str: Path to the saved file
    """
    if not stock_tips:
        logger.warning(f"No stock tips to save for {source_name}")
        return None
    
    # Create test_results directory if it doesn't exist
    output_dir = "test_results"
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_path = os.path.join(output_dir, f"{source_name}_test_{timestamp}.json")
    
    # Save to JSON
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(stock_tips, f, indent=2)
        logger.info(f"Saved test results to {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Error saving test results: {e}")
        return None

def test_all_scrapers():
    """Test all scrapers and save results"""
    all_results = {}
    
    for source in TARGET_SOURCES:
        logger.info(f"Testing {source} scraper...")
        stock_tips = test_scraper(source)
        all_results[source] = stock_tips
        
        # Save individual results
        if stock_tips:
            save_test_results(stock_tips, source)
            
            # Print sample results
            print(f"\nSample of stock tips from {source}:")
            for i, tip in enumerate(stock_tips[:3]):  # Show top 3 tips
                symbol = tip.get('symbol', 'N/A')
                company = tip.get('company_name', 'N/A')
                entry = tip.get('entry_price', 'N/A')
                target = tip.get('target_price', 'N/A')
                growth = tip.get('growth_percent', 'N/A')
                growth_str = f"{growth}%" if growth is not None else 'N/A'
                rec_type = tip.get('recommendation_type', 'N/A')
                
                print(f"{i+1}. {company} ({symbol})")
                print(f"   Entry: {entry}, Target: {target}, Growth: {growth_str}")
                print(f"   Recommendation: {rec_type}")
                print("")
    
    # Combine all results
    all_stock_tips = []
    for source_tips in all_results.values():
        if source_tips:
            all_stock_tips.extend(source_tips)
    
    # Deduplicate combined results
    unique_tips = deduplicate_stock_tips(all_stock_tips)
    
    # Save combined results
    if unique_tips:
        save_test_results(unique_tips, "all_sources_combined")
        
        logger.info(f"Found a total of {len(all_stock_tips)} stock tips")
        logger.info(f"After deduplication: {len(unique_tips)} unique stock tips")
    
    return all_results

if __name__ == "__main__":
    logger.info("Starting scraper tests...")
    results = test_all_scrapers()
    logger.info("Scraper tests completed.")
