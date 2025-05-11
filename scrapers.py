# scrapers.py
# Core scraper implementations for financial websites

import requests
from bs4 import BeautifulSoup
import logging
import time
import re
import json
from urllib.parse import urlparse
from datetime import datetime

# Configure logging
log_format = '%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format)
logger = logging.getLogger(__name__)

# --- Helper Functions ---
def get_html_content(url, headers=None, retries=2, delay=3):
    """
    Fetch HTML content from a URL with retries
    
    Args:
        url (str): URL to fetch
        headers (dict): Request headers
        retries (int): Number of retry attempts
        delay (int): Delay between retries in seconds
        
    Returns:
        str: HTML content or None if failed
    """
    if headers is None: 
        headers = { 
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36'
        }
    
    for attempt in range(retries + 1):
        try: 
            response = requests.get(url, headers=headers, timeout=20)
            response.raise_for_status()
            return response.text
        except requests.exceptions.Timeout: 
            logging.warning(f"Timeout {url} attempt {attempt + 1}")
        except requests.exceptions.RequestException as e: 
            logging.error(f"Error fetching {url} attempt {attempt + 1}: {e}")
        
        if attempt < retries: 
            time.sleep(delay)
    
    logging.error(f"Failed to fetch {url}")
    return None

def clean_price(price_str):
    """
    Clean price string and convert to float
    
    Args:
        price_str: String or object containing price
        
    Returns:
        float: Cleaned price value or None if invalid
    """
    if price_str is None: 
        return None
    if isinstance(price_str, str) and price_str.strip().upper() in ['NA', 'N/A', '-']: 
        return None
    try: 
        cleaned = re.sub(r'[^\d.]', '', str(price_str))
        return float(cleaned) if cleaned else None
    except: 
        logging.warning(f"Could not clean/convert price: '{price_str}'")
        return None

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

def validate_trade_logic(entry, target, stop_loss, symbol=""):
    """
    Validate the logic of trade recommendation
    
    Args:
        entry (float): Entry price
        target (float): Target price
        stop_loss (float): Stop loss price
        symbol (str): Stock symbol for logging
        
    Returns:
        bool: True if trade logic is valid, False otherwise
    """
    if target is None or stop_loss is None: 
        logging.info(f"Lead {symbol}: Missing TGT/SL, collecting.")
        return True
    
    if target <= stop_loss: 
        logging.warning(f"Validation FAILED {symbol}: TGT ({target}) <= SL ({stop_loss}).")
        return False
    
    if entry is not None:
        if not (stop_loss < entry < target): 
            logging.info(f"Validation NOTE {symbol}: Entry ({entry}) not between SL ({stop_loss}) and TGT ({target}).")
    else: 
        logging.info(f"Validation NOTE {symbol}: Entry price missing.")
    
    return True

# --- Scraper Functions ---
def scrape_axis_ideas(url="https://simplehai.axisdirect.in/research/research-ideas/trade-ideas"):
    """
    Scrape stock recommendations from Axis Direct
    
    Args:
        url (str): URL to scrape
        
    Returns:
        list: List of stock tip dictionaries
    """
    logging.info(f"Starting scrape AxisDirect: {url}")
    html_content = get_html_content(url)
    
    if not html_content: 
        return []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    recommendations = []
    
    # Find all recommendation cards
    idea_cards = soup.find_all('li', class_='shadow-panel', id=re.compile(r'^shadow_main_\d+'))
    
    if not idea_cards: 
        logging.warning("AxisDirect: No cards found.")
        return []
    
    logging.info(f"AxisDirect: Found {len(idea_cards)} potential cards.")
    
    for card in idea_cards:
        try:
            symbol = None
            entry_price = None
            stop_loss = None
            target_price = None
            
            # Extract symbol
            symbol_tag = card.select_one('div.panel-heading-name h5.pro-name a')
            if symbol_tag: 
                symbol = extract_symbol_from_axis_text(symbol_tag.text.strip())
            else: 
                logging.warning("AxisDirect: Symbol tag not found.")
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
                logging.warning(f"AxisDirect ({symbol}): Price list structure unexpected.")
                continue
            
            # Add to recommendations if we have enough data
            if symbol: 
                recommendations.append({
                    'symbol': symbol, 
                    'entry_price': entry_price, 
                    'target_price': target_price, 
                    'stop_loss': stop_loss, 
                    'source': 'AxisDirect'
                })
            else: 
                logging.warning(f"AxisDirect: Skipping card missing Symbol.")
                
        except Exception as e: 
            logging.error(f"Error parsing AxisDirect card: {e}", exc_info=False)
            logging.debug(f"Problem HTML (Axis): {card.prettify()[:500]}")
    
    logging.info(f"Finished AxisDirect. Scraped {len(recommendations)} potential leads.")
    return recommendations

def scrape_icici_ideas(url="https://www.icicidirect.com/research/equity/investing-ideas"):
    """
    Scrape stock recommendations from ICICI Direct
    
    Args:
        url (str): URL to scrape
        
    Returns:
        list: List of stock tip dictionaries
    """
    logging.info(f"Starting scrape ICICI Direct: {url}")
    recommendations = []
    html_content = None
    
    try:
        # For ICICI Direct, we need to use Playwright to handle dynamic content
        # This implementation provides a simplified version using requests
        html_content = get_html_content(url, retries=3, delay=5)
    except Exception as e: 
        logging.error(f"Error fetching ICICI Direct: {e}")
        return []
    
    if not html_content: 
        logging.error("ICICI Direct: Failed to fetch HTML content.")
        return []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find the main table
    ideas_table = soup.find('table', id='datatableinvestingideas') or soup.find('table', class_='table-theme2')
    
    if not ideas_table: 
        logging.warning("ICICI Direct: Table not found.")
        return []
    else: 
        logging.info("ICICI Direct: Found table.")
    
    # Extract headers
    headers = []
    header_row = ideas_table.find('thead') or ideas_table.find('tr')
    
    if header_row: 
        headers = [h.text.strip().lower() for h in header_row.find_all(['th', 'td'])]
        logging.debug(f"ICICI Headers: {headers}")
    else: 
        logging.warning("ICICI Direct: Header row not found.")
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
                col_map[target_key] = headers.index(possible_header)
                found = True
                break
            except ValueError: 
                continue
                
        if not found and target_key not in ['entry_price', 'stop_loss']:
            logging.warning(f"ICICI Direct: Missing required column '{target_key}'")
            if target_key in ['symbol_text', 'target_price']: 
                missing_required = True
    
    if missing_required: 
        logging.error("ICICI Direct: Cannot proceed without Symbol or Target.")
        return []
    
    # Process data rows
    table_body = ideas_table.find('tbody')
    rows = table_body.find_all('tr', role='row') if table_body else []
    
    logging.info(f"ICICI Direct: Found {len(rows)} data rows.")
    
    for row in rows:
        try:
            cells = row.find_all('td')
            
            if len(cells) < len(col_map): 
                logging.warning(f"ICICI Direct: Skipping row, cell count mismatch")
                continue
            
            # Extract data from cells
            symbol_text = cells[col_map['symbol_text']].text.strip() if 'symbol_text' in col_map else None
            entry_price_str = cells[col_map['entry_price']].text.strip() if 'entry_price' in col_map else None
            target_price_str = cells[col_map['target_price']].text.strip() if 'target_price' in col_map else None
            stop_loss_str = cells[col_map['stop_loss']].text.strip() if 'stop_loss' in col_map else None
            
            # Process extracted data
            symbol = extract_symbol_from_axis_text(symbol_text)
            entry_price = clean_price(entry_price_str)
            target_price = clean_price(target_price_str)
            stop_loss = clean_price(stop_loss_str)
            
            # Add to recommendations if we have enough data
            if symbol: 
                recommendations.append({
                    'symbol': symbol, 
                    'entry_price': entry_price, 
                    'target_price': target_price, 
                    'stop_loss': stop_loss, 
                    'source': 'ICICI Direct'
                })
            else: 
                logging.warning(f"ICICI Direct: Skipping row missing Symbol.")
                
        except Exception as e: 
            logging.error(f"Error parsing ICICI Direct row: {e}", exc_info=False)
            logging.debug(f"Problem HTML (ICICI): {row.prettify()}")
    
    logging.info(f"Finished ICICI Direct. Scraped {len(recommendations)} potential leads.")
    return recommendations

# --- Main Test Execution ---
if __name__ == "__main__":
    logging.getLogger().setLevel(logging.INFO)
    
    axis_url = "https://simplehai.axisdirect.in/research/research-ideas/trade-ideas"
    icici_url = "https://www.icicidirect.com/research/equity/investing-ideas"
    
    all_recommendations = []
    
    print("\n--- Running Scrapers ---")
    
    print("\n--- Scraping AxisDirect ---")
    time.sleep(2)
    axis_ideas = scrape_axis_ideas(url=axis_url)
    if axis_ideas: 
        print(f"AxisDirect: Scraped {len(axis_ideas)} potential leads.")
        all_recommendations.extend(axis_ideas)
    else: 
        print("AxisDirect: Scrape failed or no leads found.")
    
    print("\n--- Scraping ICICI Direct ---")
    time.sleep(2)
    icici_ideas = scrape_icici_ideas(url=icici_url)
    if icici_ideas: 
        print(f"ICICI Direct: Scraped {len(icici_ideas)} potential leads.")
        all_recommendations.extend(icici_ideas)
    else: 
        print("ICICI Direct: Scrape failed or no leads found.")
    
    print(f"\n--- Total Potential Leads Collected: {len(all_recommendations)} ---")
    
    # Save results for reference
    if all_recommendations:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        with open(f"scraped_results_{timestamp}.json", "w") as f:
            json.dump(all_recommendations, f, indent=2)
        print(f"Results saved to scraped_results_{timestamp}.json")
    
    # Print summary of results
    if all_recommendations:
        print("\n--- Stock Recommendation Summary ---")
        for i, rec in enumerate(all_recommendations):
            symbol = rec.get('symbol', 'N/A')
            entry = rec.get('entry_price', 'N/A')
            target = rec.get('target_price', 'N/A')
            stop_loss = rec.get('stop_loss', 'N/A')
            source = rec.get('source', 'N/A')
            
            # Calculate growth percentage
            growth = "N/A"
            if isinstance(entry, (int, float)) and isinstance(target, (int, float)) and entry > 0:
                growth = f"{((target - entry) / entry) * 100:.2f}%"
            
            print(f"{i+1}. {symbol} - Entry: {entry}, Target: {target}, SL: {stop_loss}, Growth: {growth}, Source: {source}")
