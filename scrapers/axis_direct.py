#!/usr/bin/env python3
# axis_direct.py - Specialized scraper for Axis Direct

import re
import logging
import time
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime

# Utility functions
from base_scraper import clean_price, extract_stock_details

logger = logging.getLogger(__name__)

def extract_symbol_from_axis_text(text):
    """
    Extract stock symbol from text (specialized for Axis Direct format)
    
    Args:
        text (str): Text containing stock symbol
        
    Returns:
        str: Extracted symbol or None
    """
    if not text: 
        return None
    
    # Clean up the text
    cleaned_text = re.sub(r'\s+EQ$', '', text.strip(), flags=re.IGNORECASE).strip()
    
    # Handle special cases with manual mapping
    manual_symbol_map = {
        "INDIAN HOTELS CO": "INDHOTEL",
    }
    
    mapped_symbol = manual_symbol_map.get(cleaned_text.upper())
    if mapped_symbol: 
        return mapped_symbol
    
    return cleaned_text

def get_html_content(url, session=None, headers=None, retries=2, delay=3):
    """
    Fetch HTML content from a URL with retries
    
    Args:
        url (str): URL to fetch
        session: Request session (optional)
        headers (dict): Request headers
        retries (int): Number of retry attempts
        delay (int): Delay between retries in seconds
        
    Returns:
        str: HTML content or None if failed
    """
    # This function is a placeholder as we're using the AntiBlockingManager in base_scraper
    # Imported here for compatibility with the original implementation
    from base_scraper import fetch_content_with_ab
    return fetch_content_with_ab(url, timeout=30, retries=retries)

def scrape_axis_direct(soup, url):
    """
    Specialized scraper for Axis Direct website
    
    Args:
        soup (BeautifulSoup): Parsed HTML content
        url (str): URL of the page being scraped
        
    Returns:
        list: List of stock tips extracted from the page
    """
    logging.info(f"Starting scrape Axis Direct: {url}")
    recommendations = []
    domain = "axisdirect.in"
    
    # Find all recommendation cards - this is specific to Axis Direct's HTML structure
    idea_cards = soup.find_all('li', class_='shadow-panel', id=re.compile(r'^shadow_main_\d+'))
    
    if not idea_cards: 
        logging.warning("Axis Direct: No recommendation cards found.")
        return []
    
    logging.info(f"Axis Direct: Found {len(idea_cards)} potential recommendation cards.")
    
    for card in idea_cards:
        try:
            symbol = None
            entry_price = None
            stop_loss = None
            target_price = None
            company_name = None
            
            # Extract symbol
            symbol_tag = card.select_one('div.panel-heading-name h5.pro-name a')
            if symbol_tag: 
                symbol = extract_symbol_from_axis_text(symbol_tag.text.strip())
                company_name = symbol_tag.text.strip()  # Use the full text as company name
            else: 
                logging.warning("Axis Direct: Symbol tag not found.")
                continue
            
            # Extract price information
            price_list = card.select('div.panel-body ul.pd-list-50 li')
            if len(price_list) >= 4:
                # Extract entry price range
                entry_range_tag = price_list[1].find('h4', class_='pro-val-normal')
                if entry_range_tag:
                    entry_range_str = entry_range_tag.text.strip()
                    entry_parts = [clean_price(p) for p in entry_range_str.split('-')]
                    if entry_parts and entry_parts[0] is not None: 
                        entry_price = entry_parts[0]
                
                # Extract stop loss
                sl_tag = price_list[2].find('h4', id=re.compile(r'^lossPrice_\d+'))
                if sl_tag: 
                    stop_loss = clean_price(sl_tag.text.strip())
                
                # Extract target price
                target_tag = price_list[3].find('h4', id=re.compile(r'^profitPrice_\d+'))
                if target_tag: 
                    target_price = clean_price(target_tag.text.strip())
            else: 
                logging.warning(f"Axis Direct ({symbol}): Price list structure unexpected.")
                continue
            
            # Calculate growth percentage if we have both entry and target prices
            growth_percent = None
            if entry_price and target_price and entry_price > 0:
                from base_scraper import calculate_growth_percent
                growth_percent = calculate_growth_percent(entry_price, target_price)
                growth_percent = round(growth_percent, 2) if growth_percent is not None else None
            
            # Determine confidence score based on available data
            confidence = 0.5  # Default
            if symbol:
                confidence = 0.6
            if entry_price and target_price:
                confidence = 0.8
            if stop_loss:
                confidence = 0.9
            
            # Increase confidence if growth is in target range
            if growth_percent is not None:
                from base_scraper import is_target_growth_range
                if is_target_growth_range(growth_percent):
                    confidence = min(confidence + 0.1, 1.0)
            
            # Add to recommendations if we have enough data
            if symbol: 
                stock_details = {
                    'symbol': symbol,
                    'company_name': company_name,
                    'entry_price': entry_price,
                    'target_price': target_price,
                    'stop_loss': stop_loss,
                    'growth_percent': growth_percent,
                    'recommendation_type': 'buy',  # Default to buy for Axis Direct
                    'source': domain,
                    'url': url,
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'confidence': confidence
                }
                recommendations.append(stock_details)
            else: 
                logging.warning(f"Axis Direct: Skipping card missing Symbol.")
                
        except Exception as e: 
            logging.error(f"Error parsing Axis Direct card: {e}", exc_info=True)
    
    logging.info(f"Extracted {len(recommendations)} stock tips from Axis Direct")
    return recommendations

# For testing the module directly
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    )
    
    # Test URL
    test_url = "https://simplehai.axisdirect.in/research/research-ideas/trade-ideas"
    
    # Fetch HTML
    html_content = get_html_content(test_url)
    
    if html_content:
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract stock tips
        stock_tips = scrape_axis_direct(soup, test_url)
        
        # Print results
        print(f"\nFound {len(stock_tips)} stock tips from Axis Direct:")
        for i, tip in enumerate(stock_tips):
            print(f"{i+1}. {tip['symbol']} - Entry: {tip['entry_price']}, Target: {tip['target_price']}, SL: {tip['stop_loss']}")
    else:
        print("Failed to fetch content from Axis Direct")
