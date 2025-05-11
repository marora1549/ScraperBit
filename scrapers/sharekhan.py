#!/usr/bin/env python3
# sharekhan.py - Specialized scraper for Sharekhan

import re
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime

from base_scraper import clean_price, calculate_growth_percent, is_target_growth_range

logger = logging.getLogger(__name__)

def scrape_sharekhan(soup, url):
    """
    Specialized scraper for Sharekhan website
    
    Args:
        soup (BeautifulSoup): Parsed HTML content
        url (str): URL of the page being scraped
        
    Returns:
        list: List of stock tips extracted from the page
    """
    stock_tips = []
    domain = "sharekhan.com"
    
    # APPROACH 1: Look for stock recommendation tables 
    try:
        # Find all table rows in the main content
        tables = soup.find_all('table')
        logger.info(f"Found {len(tables)} tables in Sharekhan")
        
        for table in tables:
            rows = table.find_all('tr')
            logger.info(f"Found {len(rows)} rows in Sharekhan table")
            
            if len(rows) <= 1:  # Skip if just a header row
                continue
                
            # Get headers if present
            headers = []
            if rows[0].find('th'):
                headers = [th.get_text(strip=True).lower() for th in rows[0].find_all('th')]
            else:
                # Try to extract headers from first row if not explicit th elements
                headers = [td.get_text(strip=True).lower() for td in rows[0].find_all('td')]
                rows = rows[1:]  # Skip first row as it's headers
            
            # Map column indices to expected data
            col_map = {}
            for i, header in enumerate(headers):
                if any(kw in header for kw in ['company', 'stock', 'scrip']):
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
            for row_idx, row in enumerate(rows):
                # Skip header row if we already processed headers
                if row_idx == 0 and any(cell.name == 'th' for cell in row.find_all(['td', 'th'])):
                    continue
                    
                # Get all cells in the row
                cells = row.find_all('td')
                if len(cells) < max(col_map.values() or [0]) + 1:
                    continue
                
                try:
                    # Extract stock symbol - usually the first cell if not mapped
                    symbol_cell = cells[col_map.get('company', 0)]
                    symbol_text = symbol_cell.get_text(strip=True)
                    
                    # Try to extract symbol
                    symbol = None
                    symbol_match = re.search(r'\b([A-Z]{2,5})\b', symbol_text)
                    if symbol_match:
                        symbol = symbol_match.group(1)
                    else:
                        # Try to use the company name as symbol if it looks like a ticker
                        if re.match(r'^[A-Z]{2,5}$', symbol_text):
                            symbol = symbol_text
                    
                    company_name = symbol_text
                    
                    # Extract current price
                    current_price = None
                    if 'cmp' in col_map and col_map['cmp'] < len(cells):
                        price_text = cells[col_map['cmp']].get_text(strip=True)
                        price_match = re.search(r'(\d+(?:\.\d+)?)', price_text)
                        if price_match:
                            current_price = clean_price(price_match.group(1))
                    
                    # Extract target price
                    target_price = None
                    if 'target' in col_map and col_map['target'] < len(cells):
                        target_text = cells[col_map['target']].get_text(strip=True)
                        target_match = re.search(r'(\d+(?:\.\d+)?)', target_text)
                        if target_match:
                            target_price = clean_price(target_match.group(1))
                    
                    # Extract stop loss price
                    stop_loss = None
                    if 'stop_loss' in col_map and col_map['stop_loss'] < len(cells):
                        stop_text = cells[col_map['stop_loss']].get_text(strip=True)
                        stop_match = re.search(r'(\d+(?:\.\d+)?)', stop_text)
                        if stop_match:
                            stop_loss = clean_price(stop_match.group(1))
                    
                    # Extract recommendation type
                    recommendation = "buy"  # Default to buy
                    if 'recommendation' in col_map and col_map['recommendation'] < len(cells):
                        rec_text = cells[col_map['recommendation']].get_text(strip=True).lower()
                        if 'sell' in rec_text:
                            recommendation = 'sell'
                        elif 'hold' in rec_text:
                            recommendation = 'hold'
                    
                    # Calculate growth percentage
                    growth_percent = None
                    if current_price and target_price and current_price > 0:
                        growth_percent = calculate_growth_percent(current_price, target_price)
                        growth_percent = round(growth_percent, 2) if growth_percent is not None else None
                    
                    # Create stock details if we have enough info
                    if (symbol or company_name) and (current_price or target_price):
                        # Calculate confidence based on data completeness
                        confidence = 0.7  # Base level for table data
                        if symbol and (current_price and target_price):
                            confidence = 0.8
                        if stop_loss:
                            confidence = 0.85
                        
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
                            'recommendation_type': recommendation,
                            'source': domain,
                            'url': url,
                            'date': datetime.now().strftime('%Y-%m-%d'),
                            'confidence': confidence
                        }
                        
                        stock_tips.append(stock_details)
                except Exception as e:
                    logger.error(f"Error processing Sharekhan row {row_idx}: {e}")
    except Exception as e:
        logger.error(f"Error processing Sharekhan tables: {e}")
    
    # APPROACH 2: Look for stock recommendation cards/articles
    if not stock_tips:
        recommendation_items = soup.find_all(['div', 'article', 'li'], 
                                    class_=re.compile(r'(card|call|research|item|recommendation)', re.I))
        logger.info(f"Found {len(recommendation_items)} potential recommendation items in Sharekhan")
        
        for item in recommendation_items:
            try:
                item_text = item.get_text(strip=True)
                
                # Skip if too short or doesn't contain key terms
                if len(item_text) < 100 or not re.search(r'(buy|sell|hold|target|recommendation|call)', item_text.lower()):
                    continue
                
                # Extract company/symbol information
                heading = item.find(['h1', 'h2', 'h3', 'h4', 'h5', 'strong'])
                heading_text = heading.get_text(strip=True) if heading else ""
                
                company_name = None
                symbol = None
                
                # Try to extract from heading first
                if heading_text:
                    # Check for symbol pattern
                    symbol_match = re.search(r'\b([A-Z]{2,5})\b', heading_text)
                    if symbol_match:
                        symbol = symbol_match.group(1)
                        company_name = heading_text
                    
                    # If no symbol but has company name pattern
                    if not symbol:
                        company_match = re.search(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,}(?:\s+Ltd\.?)?)', heading_text)
                        if company_match:
                            company_name = company_match.group(1)
                
                # If not found in heading, search in body text
                if not symbol:
                    symbol_matches = re.findall(r'\b([A-Z]{2,5})\b', item_text)
                    filtered_symbols = [s for s in symbol_matches if s not in ['BUY', 'SELL', 'HOLD', 'CMP', 'NSE', 'BSE']]
                    if filtered_symbols:
                        symbol = filtered_symbols[0]
                
                if not company_name:
                    company_matches = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,}(?:\s+Ltd\.?)?)', item_text)
                    if company_matches:
                        company_name = company_matches[0]
                
                # Extract prices
                price_matches = re.findall(r'(?:Rs\.?|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)', item_text)
                prices = [clean_price(p) for p in price_matches if clean_price(p) is not None]
                
                current_price = None
                target_price = None
                stop_loss = None
                
                # Try to find specific price indicators
                cmp_match = re.search(r'(?:CMP|current price|price)[:\s]*(?:Rs\.?|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)', item_text.lower())
                if cmp_match:
                    current_price = clean_price(cmp_match.group(1))
                
                target_match = re.search(r'(?:target|price target)[:\s]*(?:Rs\.?|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)', item_text.lower())
                if target_match:
                    target_price = clean_price(target_match.group(1))
                
                sl_match = re.search(r'(?:stop loss|sl)[:\s]*(?:Rs\.?|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)', item_text.lower())
                if sl_match:
                    stop_loss = clean_price(sl_match.group(1))
                
                # If specific patterns didn't work but we have prices, make educated guesses
                if not current_price and not target_price and len(prices) >= 2:
                    # Assume the first is current, second is target
                    current_price = prices[0]
                    target_price = prices[1]
                    if len(prices) >= 3:
                        stop_loss = prices[2]
                
                # Determine recommendation type
                recommendation = "buy"  # Default
                if 'sell' in item_text.lower():
                    recommendation = 'sell'
                elif 'hold' in item_text.lower():
                    recommendation = 'hold'
                
                # Calculate growth percentage
                growth_percent = None
                if current_price and target_price and current_price > 0:
                    growth_percent = calculate_growth_percent(current_price, target_price)
                    growth_percent = round(growth_percent, 2) if growth_percent is not None else None
                
                # Create stock details if we have enough info
                if (symbol or company_name) and (current_price or target_price):
                    # Calculate confidence based on data completeness
                    confidence = 0.6  # Base level for card/text data
                    if symbol and company_name:
                        confidence = 0.65
                    if current_price and target_price:
                        confidence = 0.75
                    if stop_loss:
                        confidence = 0.8
                    
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
                        'recommendation_type': recommendation,
                        'source': domain,
                        'url': url,
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'confidence': confidence
                    }
                    
                    stock_tips.append(stock_details)
            except Exception as e:
                logger.error(f"Error processing Sharekhan recommendation item: {e}")
    
    # Deduplicate based on symbol
    final_tips = []
    seen_symbols = set()
    
    for tip in stock_tips:
        symbol = tip.get('symbol')
        if symbol and symbol not in seen_symbols:
            final_tips.append(tip)
            seen_symbols.add(symbol)
    
    logger.info(f"Extracted {len(final_tips)} stock tips from Sharekhan")
    return final_tips

# For testing the module directly
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    )
    
    # Test URL
    test_url = "https://old.sharekhan.com/research/latest-call/investor-research"
    
    # Fetch HTML
    from base_scraper import fetch_content_with_ab
    html_content = fetch_content_with_ab(test_url)
    
    if html_content:
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract stock tips
        stock_tips = scrape_sharekhan(soup, test_url)
        
        # Print results
        print(f"\nFound {len(stock_tips)} stock tips from Sharekhan:")
        for i, tip in enumerate(stock_tips):
            growth_str = f"{tip['growth_percent']}%" if tip['growth_percent'] is not None else "N/A"
            print(f"{i+1}. {tip.get('company_name')} ({tip.get('symbol')}) - Entry: {tip['entry_price']}, Target: {tip['target_price']}, Growth: {growth_str}")
    else:
        print("Failed to fetch content from Sharekhan")
