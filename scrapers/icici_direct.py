#!/usr/bin/env python3
# icici_direct.py - Specialized scraper for ICICI Direct

import re
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime

from base_scraper import clean_price, calculate_growth_percent, is_target_growth_range

logger = logging.getLogger(__name__)

def extract_symbol_from_text(text):
    """
    Extract stock symbol from text
    
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

def scrape_icici_direct(soup, url):
    """
    Specialized scraper for ICICI Direct website
    
    Args:
        soup (BeautifulSoup): Parsed HTML content
        url (str): URL of the page being scraped
        
    Returns:
        list: List of stock tips extracted from the page
    """
    logger.info(f"Starting scrape ICICI Direct: {url}")
    recommendations = []
    domain = "icicidirect.com"
    
    # Find the main table
    ideas_table = soup.find('table', id='datatableinvestingideas') or soup.find('table', class_='table-theme2')
    
    if not ideas_table: 
        logger.warning("ICICI Direct: Table not found.")
        return []
    
    logger.info("ICICI Direct: Found table.")
    
    # Extract headers
    headers = []
    header_row = ideas_table.find('thead') or ideas_table.find('tr')
    
    if header_row: 
        headers = [h.text.strip().lower() for h in header_row.find_all(['th', 'td'])]
        logger.debug(f"ICICI Headers: {headers}")
    else: 
        logger.warning("ICICI Direct: Header row not found.")
        return []
    
    # Map column indices
    col_map = {}
    expected_cols = {
        'symbol_text': ['company', 'stock name', 'symbol', 'scrip'], 
        'entry_price': ['entry price', 'entry', 'buy price', 'recommended price', 'cmp'], 
        'target_price': ['target price', 'target'], 
        'stop_loss': ['stop loss', 'sl']
    }
    
    missing_required = False
    for target_key, possible_headers in expected_cols.items():
        found = False
        for possible_header in possible_headers:
            try: 
                col_idx = next((i for i, h in enumerate(headers) if possible_header in h), None)
                if col_idx is not None:
                    col_map[target_key] = col_idx
                    found = True
                    break
            except: 
                continue
                
        if not found and target_key not in ['entry_price', 'stop_loss']:
            logger.warning(f"ICICI Direct: Missing required column '{target_key}'")
            if target_key in ['symbol_text', 'target_price']: 
                missing_required = True
    
    if missing_required: 
        logger.error("ICICI Direct: Cannot proceed without Symbol or Target.")
        return []
    
    # Process data rows
    table_body = ideas_table.find('tbody')
    rows = table_body.find_all('tr') if table_body else ideas_table.find_all('tr')[1:] if ideas_table.find_all('tr') else []
    
    logger.info(f"ICICI Direct: Found {len(rows)} data rows.")
    
    for row in rows:
        try:
            cells = row.find_all('td')
            
            if len(cells) < max(col_map.values() or [0]) + 1: 
                continue
            
            # Extract data from cells
            symbol_text = cells[col_map.get('symbol_text', 0)].text.strip() if 'symbol_text' in col_map else None
            entry_price_str = cells[col_map.get('entry_price', 0)].text.strip() if 'entry_price' in col_map else None
            target_price_str = cells[col_map.get('target_price', 0)].text.strip() if 'target_price' in col_map else None
            stop_loss_str = cells[col_map.get('stop_loss', 0)].text.strip() if 'stop_loss' in col_map else None
            
            # Process extracted data
            symbol = extract_symbol_from_text(symbol_text)
            company_name = symbol_text
            entry_price = clean_price(entry_price_str)
            target_price = clean_price(target_price_str)
            stop_loss = clean_price(stop_loss_str)
            
            # Calculate growth percentage
            growth_percent = None
            if entry_price and target_price and entry_price > 0:
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
            if growth_percent is not None and is_target_growth_range(growth_percent):
                confidence = min(confidence + 0.1, 1.0)
            
            # Add to recommendations if we have enough data
            if symbol and (entry_price or target_price): 
                stock_details = {
                    'symbol': symbol,
                    'company_name': company_name,
                    'entry_price': entry_price,
                    'target_price': target_price,
                    'stop_loss': stop_loss,
                    'growth_percent': growth_percent,
                    'recommendation_type': 'buy',  # Default to buy
                    'source': domain,
                    'url': url,
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'confidence': confidence
                }
                recommendations.append(stock_details)
                
        except Exception as e: 
            logger.error(f"Error parsing ICICI Direct row: {e}", exc_info=True)
    
    logger.info(f"Extracted {len(recommendations)} stock tips from ICICI Direct")
    return recommendations

# For testing the module directly
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    )
    
    # Test URL
    test_url = "https://www.icicidirect.com/research/equity/investing-ideas"
    
    # Fetch HTML
    from base_scraper import fetch_content_with_ab
    html_content = fetch_content_with_ab(test_url)
    
    if html_content:
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract stock tips
        stock_tips = scrape_icici_direct(soup, test_url)
        
        # Print results
        print(f"\nFound {len(stock_tips)} stock tips from ICICI Direct:")
        for i, tip in enumerate(stock_tips):
            print(f"{i+1}. {tip['symbol']} - Entry: {tip['entry_price']}, Target: {tip['target_price']}, SL: {tip['stop_loss']}")
    else:
        print("Failed to fetch content from ICICI Direct")
