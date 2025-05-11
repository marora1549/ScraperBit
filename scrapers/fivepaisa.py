#!/usr/bin/env python3
# fivepaisa.py - Specialized scraper for 5paisa

import re
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime

from base_scraper import clean_price, calculate_growth_percent, is_target_growth_range

logger = logging.getLogger(__name__)

def scrape_5paisa(soup, url):
    """
    Specialized scraper for 5paisa website
    
    Args:
        soup (BeautifulSoup): Parsed HTML content
        url (str): URL of the page being scraped
        
    Returns:
        list: List of stock tips extracted from the page
    """
    stock_tips = []
    domain = "5paisa.com"
    
    # 5paisa typically presents stock recommendations in tables
    tables = soup.find_all('table')
    logger.info(f"Found {len(tables)} tables in 5paisa")
    
    # Process tables
    for table_idx, table in enumerate(tables):
        try:
            rows = table.find_all('tr')
            if len(rows) <= 1:  # Skip if only header row
                continue
            
            # Try to get headers
            headers = [th.get_text(strip=True).lower() for th in rows[0].find_all(['th', 'td'])]
            
            # Map columns to expected data
            col_map = {}
            for i, header in enumerate(headers):
                if any(kw in header for kw in ['company', 'stock', 'name']):
                    col_map['company'] = i
                elif any(kw in header for kw in ['cmp', 'price', 'ltp', 'current']):
                    col_map['cmp'] = i
                elif any(kw in header for kw in ['target']):
                    col_map['target'] = i
                elif any(kw in header for kw in ['stop', 'sl']):
                    col_map['stop_loss'] = i
                elif any(kw in header for kw in ['view', 'recommendation', 'call']):
                    col_map['recommendation'] = i
            
            # Process data rows
            for row_idx, row in enumerate(rows[1:], 1):
                cells = row.find_all(['td', 'th'])
                if len(cells) < len(headers):
                    continue
                
                # Extract data based on column mapping
                company_name = cells[col_map.get('company', 0)].get_text(strip=True)
                
                # Try to extract symbol from company name
                symbol = None
                symbol_match = re.search(r'\(([A-Z]{2,5})\)', company_name)
                if symbol_match:
                    symbol = symbol_match.group(1)
                else:
                    # Check if first word is a symbol
                    first_word = company_name.split()[0] if company_name else ""
                    if re.match(r'^[A-Z]{2,5}$', first_word):
                        symbol = first_word
                
                # Extract prices
                current_price = None
                if 'cmp' in col_map:
                    current_price = clean_price(cells[col_map['cmp']].get_text(strip=True))
                
                target_price = None
                if 'target' in col_map:
                    target_price = clean_price(cells[col_map['target']].get_text(strip=True))
                
                stop_loss = None
                if 'stop_loss' in col_map:
                    stop_loss = clean_price(cells[col_map['stop_loss']].get_text(strip=True))
                
                # Determine recommendation type
                rec_type = 'buy'  # Default
                if 'recommendation' in col_map:
                    rec_text = cells[col_map['recommendation']].get_text(strip=True).lower()
                    if 'sell' in rec_text or 'reduce' in rec_text:
                        rec_type = 'sell'
                    elif 'hold' in rec_text or 'neutral' in rec_text:
                        rec_type = 'hold'
                
                # Calculate growth percentage
                growth_percent = None
                if current_price and target_price and current_price > 0:
                    growth_percent = calculate_growth_percent(current_price, target_price)
                    growth_percent = round(growth_percent, 2) if growth_percent is not None else None
                
                # Create stock details if we have enough info
                if company_name and (target_price or current_price):
                    # Determine confidence score based on available data
                    confidence = 0.7  # Base level for table data
                    if symbol:
                        confidence = max(confidence, 0.75)
                    if current_price and target_price:
                        confidence = max(confidence, 0.85)
                    if stop_loss:
                        confidence = max(confidence, 0.9)
                    
                    # Bonus confidence if in target range
                    if is_target_growth_range(growth_percent):
                        confidence = min(confidence + 0.15, 1.0)
                    
                    stock_details = {
                        'symbol': symbol,
                        'company_name': company_name,
                        'entry_price': current_price,
                        'target_price': target_price,
                        'stop_loss': stop_loss,
                        'growth_percent': growth_percent,
                        'recommendation_type': rec_type,
                        'source': domain,
                        'url': url,
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'confidence': confidence
                    }
                    
                    stock_tips.append(stock_details)
        except Exception as e:
            logger.error(f"Error processing 5paisa table {table_idx}: {e}", exc_info=True)
    
    # If no stock tips from tables, try to find recommendation cards
    if not stock_tips:
        # Look for stock recommendation cards
        stock_cards = soup.find_all(['div', 'li'], 
                             class_=re.compile(r'(card|recommendation|stock|pick|listing-item)', re.I))
        logger.info(f"Found {len(stock_cards)} stock recommendation cards in 5paisa")
        
        for card_idx, card in enumerate(stock_cards):
            try:
                card_text = card.get_text(separator=' ', strip=True)
                
                # Skip if too short
                if len(card_text) < 50:
                    continue
                
                # Check if this looks like a stock recommendation
                if not re.search(r'(buy|sell|hold|target|current price|cmp|stop loss|sl)', card_text.lower()):
                    continue
                
                # Extract stock details using pattern matching
                # Company name and symbol
                company_matches = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,}(?:\s+Ltd\.?)?)', card_text)
                company_name = company_matches[0] if company_matches else None
                
                symbol_matches = re.findall(r'\b([A-Z]{2,5})\b', card_text)
                symbol = symbol_matches[0] if symbol_matches else None
                
                # Price information
                price_matches = re.findall(r'(?:Rs\.?|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)', card_text)
                prices = [clean_price(p) for p in price_matches]
                
                current_price = prices[0] if len(prices) > 0 else None
                target_price = prices[1] if len(prices) > 1 else None
                stop_loss = prices[2] if len(prices) > 2 else None
                
                # Determine recommendation
                rec_type = 'buy'  # Default
                if 'sell' in card_text.lower() or 'reduce' in card_text.lower():
                    rec_type = 'sell'
                elif 'hold' in card_text.lower() or 'neutral' in card_text.lower():
                    rec_type = 'hold'
                
                # Calculate growth
                growth_percent = None
                if current_price and target_price and current_price > 0:
                    growth_percent = calculate_growth_percent(current_price, target_price)
                    growth_percent = round(growth_percent, 2) if growth_percent is not None else None
                
                # Create stock details if we have enough info
                if (symbol or company_name) and (current_price or target_price):
                    # Determine confidence score based on available data
                    confidence = 0.6  # Base level for card data (less structured)
                    if symbol and company_name:
                        confidence = max(confidence, 0.7)
                    if current_price and target_price:
                        confidence = max(confidence, 0.8)
                    
                    # Bonus confidence if in target range
                    if is_target_growth_range(growth_percent):
                        confidence = min(confidence + 0.15, 1.0)
                    
                    stock_details = {
                        'symbol': symbol,
                        'company_name': company_name,
                        'entry_price': current_price,
                        'target_price': target_price,
                        'stop_loss': stop_loss,
                        'growth_percent': growth_percent,
                        'recommendation_type': rec_type,
                        'source': domain,
                        'url': url,
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'confidence': confidence
                    }
                    
                    stock_tips.append(stock_details)
            except Exception as e:
                logger.error(f"Error processing 5paisa card {card_idx}: {e}", exc_info=True)
    
    # Deduplicate based on symbol and company name
    final_tips = []
    seen_signatures = set()
    
    for tip in stock_tips:
        # Create a signature for deduplication
        sig = (str(tip.get('symbol', '')), str(tip.get('company_name', '')))
        if sig not in seen_signatures:
            final_tips.append(tip)
            seen_signatures.add(sig)
    
    logger.info(f"Extracted {len(final_tips)} stock tips from 5paisa")
    return final_tips

# For testing the module directly
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    )
    
    # Test URL
    test_url = "https://www.5paisa.com/share-market-today/stocks-to-buy-or-sell-today"
    
    # Fetch HTML
    from base_scraper import fetch_content_with_ab
    html_content = fetch_content_with_ab(test_url)
    
    if html_content:
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract stock tips
        stock_tips = scrape_5paisa(soup, test_url)
        
        # Print results
        print(f"\nFound {len(stock_tips)} stock tips from 5paisa:")
        for i, tip in enumerate(stock_tips):
            growth_str = f"{tip['growth_percent']}%" if tip['growth_percent'] is not None else "N/A"
            print(f"{i+1}. {tip.get('company_name')} ({tip.get('symbol')}) - Entry: {tip['entry_price']}, Target: {tip['target_price']}, Growth: {growth_str}")
    else:
        print("Failed to fetch content from 5paisa")
