#!/usr/bin/env python3
# moneycontrol.py - Specialized scraper for MoneyControl

import re
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime

from base_scraper import clean_price, calculate_growth_percent, is_target_growth_range

logger = logging.getLogger(__name__)

def scrape_moneycontrol(soup, url):
    """
    Specialized scraper for MoneyControl website
    
    Args:
        soup (BeautifulSoup): Parsed HTML content
        url (str): URL of the page being scraped
        
    Returns:
        list: List of stock tips extracted from the page
    """
    stock_tips = []
    domain = "moneycontrol.com"
    
    # APPROACH 1: Look for stock recommendation cards
    stock_cards = soup.find_all(['div', 'article'], 
                         class_=re.compile(r'(card|stockCardCont|story_list|article_box|stock-idea)', re.I))
    
    logger.info(f"Found {len(stock_cards)} potential stock cards in MoneyControl")
    
    for card in stock_cards:
        try:
            # Skip if too small to be a recommendation card
            card_text = card.get_text(strip=True)
            if not card_text or len(card_text) < 50:
                continue
            
            # Check if it contains stock recommendation keywords
            if not re.search(r'(buy|sell|hold|target|recommendation|call|price)', card_text.lower()):
                continue
            
            # Extract recommendation date if available
            date_element = card.find(['span', 'div'], string=re.compile(r'Reco on', re.I)) or \
                          card.find(['span', 'div'], class_=re.compile(r'(date|time)', re.I))
            
            # Extract symbol/stock name from heading
            heading = card.find(['h1', 'h2', 'h3', 'h4', 'a'], class_=re.compile(r'(heading|title|headline)', re.I))
            if not heading:
                heading = card.find(['h1', 'h2', 'h3', 'h4', 'a'])
            
            heading_text = heading.get_text(strip=True) if heading else ""
            
            # If no clear heading, try other approaches to find stock name
            if not heading_text:
                subheadings = card.find_all(['h5', 'h6', 'strong', 'b'])
                for subheading in subheadings:
                    if len(subheading.get_text(strip=True)) > 0:
                        heading_text = subheading.get_text(strip=True)
                        break
            
            company_name = None
            symbol = None
            
            # Extract company name and symbol from heading
            if heading_text:
                # Check for stock symbol pattern
                symbol_match = re.search(r'\b([A-Z]{2,5})\b', heading_text)
                if symbol_match:
                    symbol = symbol_match.group(1)
                    if symbol in ['BUY', 'SELL', 'HOLD']:  # Skip if it's just a recommendation
                        symbol = None
                
                # Get company name from heading
                company_name = heading_text
            
            # If no symbol from heading, look in the card text
            if not symbol:
                symbol_matches = re.findall(r'\b([A-Z]{2,5})\b', card_text)
                filtered_symbols = [s for s in symbol_matches if s not in ['BUY', 'SELL', 'HOLD', 'CMP', 'NSE', 'BSE']]
                if filtered_symbols:
                    symbol = filtered_symbols[0]
            
            # Determine recommendation type
            recommendation = "buy"  # Default to buy
            
            if re.search(r'\b(buy|bullish|accumulate)\b', card_text.lower()):
                recommendation = 'buy'
            elif re.search(r'\b(sell|bearish|reduce)\b', card_text.lower()):
                recommendation = 'sell'
            elif re.search(r'\b(hold|neutral)\b', card_text.lower()):
                recommendation = 'hold'
            
            # Extract prices using various approaches
            
            # 1. Look for labeled price sections
            price_elements = []
            
            # Check for price labels
            price_elements = card.find_all(['div', 'span', 'p'], 
                                   string=re.compile(r'(CMP|Current Price|Target Price|Stop Loss)', re.I))
            
            current_price = None
            target_price = None
            stop_loss = None
            
            for elem in price_elements:
                elem_text = elem.get_text(strip=True)
                
                if re.search(r'CMP|Current Price', elem_text, re.I):
                    price_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', elem_text)
                    if price_match:
                        current_price = clean_price(price_match.group(1))
                
                elif re.search(r'Target', elem_text, re.I):
                    price_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', elem_text)
                    if price_match:
                        target_price = clean_price(price_match.group(1))
                
                elif re.search(r'Stop Loss|SL', elem_text, re.I):
                    price_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', elem_text)
                    if price_match:
                        stop_loss = clean_price(price_match.group(1))
            
            # 2. If specific labels don't work, try pattern matching in the full text
            if not current_price:
                cmp_match = re.search(r'(?:CMP|Current Price)[:\s]*(?:Rs\.?|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)', card_text, re.I)
                if cmp_match:
                    current_price = clean_price(cmp_match.group(1))
            
            if not target_price:
                target_match = re.search(r'(?:Target)[:\s]*(?:Rs\.?|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)', card_text, re.I)
                if target_match:
                    target_price = clean_price(target_match.group(1))
            
            if not stop_loss:
                sl_match = re.search(r'(?:Stop Loss|SL)[:\s]*(?:Rs\.?|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)', card_text, re.I)
                if sl_match:
                    stop_loss = clean_price(sl_match.group(1))
            
            # 3. If specific patterns don't work, try to find all prices and make educated guesses
            if not current_price or not target_price:
                price_matches = re.findall(r'(?:Rs\.?|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)', card_text)
                prices = [clean_price(p) for p in price_matches if clean_price(p) is not None]
                
                if len(prices) >= 2 and not current_price and not target_price:
                    # Assume first is current, second is target
                    current_price = prices[0]
                    target_price = prices[1]
                    
                    # If there's a third price and no stop loss, it might be the stop loss
                    if len(prices) >= 3 and not stop_loss:
                        stop_loss = min(prices[2:])  # Use the smallest remaining price as stop loss
            
            # Calculate growth percentage
            growth_percent = None
            if current_price and target_price and current_price > 0:
                growth_percent = calculate_growth_percent(current_price, target_price)
                growth_percent = round(growth_percent, 2) if growth_percent is not None else None
            
            # Create stock details if we have enough info
            if (symbol or company_name) and (current_price or target_price):
                # Calculate confidence based on data completeness
                confidence = 0.6  # Base level for card data
                if symbol:
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
            logger.error(f"Error processing MoneyControl card: {e}", exc_info=True)
    
    # APPROACH 2: Look for stock tables
    tables = soup.find_all('table')
    logger.info(f"Found {len(tables)} tables in MoneyControl")
    
    for table_idx, table in enumerate(tables):
        try:
            rows = table.find_all('tr')
            if len(rows) <= 1:  # Skip if just a header row
                continue
            
            # Check if this looks like a stock recommendation table
            header_row = rows[0]
            headers = [th.get_text(strip=True).lower() for th in header_row.find_all(['th', 'td'])]
            
            # Check if headers indicate stock data
            if not any(h in ['stock', 'company', 'symbol', 'reco', 'target', 'price'] for h in headers):
                continue
            
            # Map columns to expected data
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
            data_rows = rows[1:]  # Skip header
            
            for row_idx, row in enumerate(data_rows):
                cells = row.find_all(['td', 'th'])
                if len(cells) < 3:  # Need minimum cells for meaningful data
                    continue
                
                # Extract data based on column positions or mapping
                company_name = cells[col_map.get('company', 0)].get_text(strip=True) if 'company' in col_map else cells[0].get_text(strip=True)
                
                # Try to extract symbol from company name
                symbol = None
                symbol_match = re.search(r'\b([A-Z]{2,5})\b', company_name)
                if symbol_match:
                    symbol = symbol_match.group(1)
                    if symbol in ['BUY', 'SELL', 'HOLD']:  # Skip if it's just a recommendation
                        symbol = None
                
                # Extract prices
                current_price = None
                target_price = None
                stop_loss = None
                
                # Use column mapping if available
                if 'cmp' in col_map and col_map['cmp'] < len(cells):
                    current_price = clean_price(cells[col_map['cmp']].get_text(strip=True))
                
                if 'target' in col_map and col_map['target'] < len(cells):
                    target_price = clean_price(cells[col_map['target']].get_text(strip=True))
                
                if 'stop_loss' in col_map and col_map['stop_loss'] < len(cells):
                    stop_loss = clean_price(cells[col_map['stop_loss']].get_text(strip=True))
                
                # If mapping doesn't work, try to determine prices from cell text
                if not current_price and not target_price:
                    # Collect all prices from the row
                    all_prices = []
                    for cell in cells:
                        price_matches = re.findall(r'(\d+(?:,\d+)*(?:\.\d+)?)', cell.get_text(strip=True))
                        if price_matches:
                            price = clean_price(price_matches[0])
                            if price:
                                all_prices.append(price)
                    
                    # If we found at least two prices, assume first is current, second is target
                    if len(all_prices) >= 2:
                        current_price = all_prices[0]
                        target_price = all_prices[1]
                
                # Determine recommendation type
                rec_type = "buy"  # Default
                
                for cell in cells:
                    cell_text = cell.get_text(strip=True).lower()
                    if 'buy' in cell_text or 'bullish' in cell_text:
                        rec_type = 'buy'
                        break
                    elif 'sell' in cell_text or 'bearish' in cell_text:
                        rec_type = 'sell'
                        break
                    elif 'hold' in cell_text or 'neutral' in cell_text:
                        rec_type = 'hold'
                        break
                
                # Calculate growth percentage
                growth_percent = None
                if current_price and target_price and current_price > 0:
                    growth_percent = calculate_growth_percent(current_price, target_price)
                    growth_percent = round(growth_percent, 2) if growth_percent is not None else None
                
                # Create stock details if we have enough info
                if (symbol or company_name) and (current_price or target_price):
                    # Calculate confidence based on data completeness
                    confidence = 0.7  # Base level for table data
                    if symbol:
                        confidence = 0.75
                    if current_price and target_price:
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
                        'recommendation_type': rec_type,
                        'source': domain,
                        'url': url,
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'confidence': confidence
                    }
                    
                    stock_tips.append(stock_details)
        except Exception as e:
            logger.error(f"Error processing MoneyControl table {table_idx}: {e}", exc_info=True)
    
    # Deduplicate based on symbol
    final_tips = []
    seen_symbols = set()
    
    for tip in stock_tips:
        symbol = tip.get('symbol')
        if symbol and symbol not in seen_symbols:
            final_tips.append(tip)
            seen_symbols.add(symbol)
        elif not symbol and tip not in final_tips:  # If no symbol, check complete object
            final_tips.append(tip)
    
    logger.info(f"Extracted {len(final_tips)} stock tips from MoneyControl")
    return final_tips

# For testing the module directly
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    )
    
    # Test URL
    test_url = "https://www.moneycontrol.com/markets/stock-ideas/"
    
    # Fetch HTML
    from base_scraper import fetch_content_with_ab
    html_content = fetch_content_with_ab(test_url)
    
    if html_content:
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract stock tips
        stock_tips = scrape_moneycontrol(soup, test_url)
        
        # Print results
        print(f"\nFound {len(stock_tips)} stock tips from MoneyControl:")
        for i, tip in enumerate(stock_tips):
            growth_str = f"{tip['growth_percent']}%" if tip['growth_percent'] is not None else "N/A"
            print(f"{i+1}. {tip.get('company_name')} ({tip.get('symbol')}) - Entry: {tip['entry_price']}, Target: {tip['target_price']}, Growth: {growth_str}")
    else:
        print("Failed to fetch content from MoneyControl")
