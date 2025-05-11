#!/usr/bin/env python3
# kotak_securities.py - Specialized scraper for Kotak Securities

import re
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from datetime import datetime

from base_scraper import clean_price, calculate_growth_percent, is_target_growth_range

logger = logging.getLogger(__name__)

def scrape_kotak_securities(soup, url):
    """
    Specialized scraper for Kotak Securities website
    
    Args:
        soup (BeautifulSoup): Parsed HTML content
        url (str): URL of the page being scraped
        
    Returns:
        list: List of stock tips extracted from the page
    """
    stock_tips = []
    domain = "kotaksecurities.com"
    
    # APPROACH 1: Look for research cards or containers
    research_containers = soup.find_all(['div', 'section'], class_=re.compile(r'(research|card|report|stock|equity)', re.I))
    logger.info(f"Found {len(research_containers)} potential research containers in Kotak Securities")

    # APPROACH 2: Look for tables which often contain stock recommendations
    tables = soup.find_all('table')
    logger.info(f"Found {len(tables)} tables in Kotak Securities")

    # Process tables first as they're more likely to have structured data
    for table in tables:
        rows = table.find_all('tr')
        if len(rows) <= 1:  # Skip if only header row
            continue

        # Try to determine header row and column structure
        header_cells = rows[0].find_all(['th', 'td'])
        headers = [cell.get_text(strip=True).lower() for cell in header_cells]

        # Look for common column names in stock recommendation tables
        col_map = {}
        for i, header in enumerate(headers):
            if any(kw in header for kw in ['company', 'stock', 'scrip']):
                col_map['company'] = i
            elif any(kw in header for kw in ['cmp', 'price', 'current']):
                col_map['cmp'] = i
            elif any(kw in header for kw in ['target']):
                col_map['target'] = i
            elif any(kw in header for kw in ['recommendation', 'rating', 'call']):
                col_map['recommendation'] = i

        # Process data rows if we found relevant columns
        if 'company' in col_map and ('target' in col_map or 'cmp' in col_map):
            for row in rows[1:]:
                cells = row.find_all(['td', 'th'])
                if len(cells) <= max(col_map.values()):
                    continue

                # Extract data
                company_name = cells[col_map['company']].get_text(strip=True)
                current_price = clean_price(cells[col_map.get('cmp', -1)].get_text(strip=True)) if 'cmp' in col_map else None
                target_price = clean_price(cells[col_map.get('target', -1)].get_text(strip=True)) if 'target' in col_map else None

                # Try to extract symbol from company name
                symbol_match = re.search(r'^\s*([A-Z]{2,5})\b', company_name)
                symbol = symbol_match.group(1) if symbol_match else None

                # Determine recommendation type
                rec_type = 'buy'  # Default to buy
                if 'recommendation' in col_map:
                    rec_text = cells[col_map['recommendation']].get_text(strip=True).lower()
                    if any(kw in rec_text for kw in ['sell', 'reduce']):
                        rec_type = 'sell'
                    elif any(kw in rec_text for kw in ['hold', 'neutral']):
                        rec_type = 'hold'

                # Calculate growth if we have both prices
                growth_percent = None
                if current_price and target_price and current_price > 0:
                    growth_percent = calculate_growth_percent(current_price, target_price)
                    growth_percent = round(growth_percent, 2) if growth_percent is not None else None

                # Create stock details if we have enough data
                if (symbol or company_name) and (target_price or current_price):
                    # Determine confidence score
                    confidence = 0.7  # Base confidence for table data
                    if symbol and (current_price and target_price):
                        confidence = 0.8
                    if is_target_growth_range(growth_percent):
                        confidence = min(confidence + 0.15, 1.0)
                        
                    stock_details = {
                        'symbol': symbol,
                        'company_name': company_name,
                        'entry_price': current_price,
                        'target_price': target_price,
                        'stop_loss': None,  # Not typically provided in Kotak tables
                        'growth_percent': growth_percent,
                        'recommendation_type': rec_type,
                        'source': domain,
                        'url': url,
                        'date': datetime.now().strftime('%Y-%m-%d'),
                        'confidence': confidence
                    }

                    stock_tips.append(stock_details)

    # If tables didn't work, process other containers
    if not stock_tips:
        # Look for research report cards or articles
        for container in research_containers:
            container_text = container.get_text(strip=True)

            # Skip if not enough text or doesn't look like a stock recommendation
            if len(container_text) < 100 or not re.search(r'(buy|sell|hold|target|recommendation)', container_text.lower()):
                continue

            # Try to find specific sections like heading/title
            heading = container.find(['h1', 'h2', 'h3', 'h4', 'strong', 'b'])
            heading_text = heading.get_text(strip=True) if heading else ""

            # Extract stock details
            # Company name and symbol
            company_matches = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,}(?:\s+Ltd\.?)?)', container_text)
            company_name = company_matches[0] if company_matches else None
            
            symbol_matches = re.findall(r'\b([A-Z]{2,5})\b', container_text)
            filtered_symbols = [s for s in symbol_matches if s not in ['BUY', 'SELL', 'HOLD', 'CMP', 'NSE', 'BSE']]
            symbol = filtered_symbols[0] if filtered_symbols else None
            
            # Extract prices using pattern matching
            price_patterns = re.findall(r'(?:Rs\.?|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)', container_text)
            prices = [clean_price(p) for p in price_patterns]
            
            # Try to identify which price is which
            current_price = None
            target_price = None
            
            # Look for specific markers
            cmp_match = re.search(r'(?:CMP|current price)[:\s]*(?:Rs\.?|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)', container_text.lower())
            if cmp_match:
                current_price = clean_price(cmp_match.group(1))
                
            target_match = re.search(r'(?:target|price target)[:\s]*(?:Rs\.?|₹)?\s*(\d+(?:,\d+)*(?:\.\d+)?)', container_text.lower())
            if target_match:
                target_price = clean_price(target_match.group(1))
            
            # If specific patterns didn't work but we have prices, make educated guesses
            if (not current_price or not target_price) and len(prices) >= 2:
                # Usually the lower price is current and higher is target
                sorted_prices = sorted(prices)
                if not current_price and len(sorted_prices) > 0:
                    current_price = sorted_prices[0]
                if not target_price and len(sorted_prices) > 1:
                    target_price = sorted_prices[-1]

            # Determine recommendation type
            rec_type = 'buy'  # Default
            if 'buy' in container_text.lower():
                rec_type = 'buy'
            elif 'sell' in container_text.lower():
                rec_type = 'sell'
            elif 'hold' in container_text.lower():
                rec_type = 'hold'

            # Calculate growth percent
            growth_percent = None
            if current_price and target_price and current_price > 0:
                growth_percent = calculate_growth_percent(current_price, target_price)
                growth_percent = round(growth_percent, 2) if growth_percent is not None else None

            # Create stock details if we have enough information
            if (symbol or company_name) and (target_price or current_price):
                # Determine confidence score
                confidence = 0.5  # Base confidence for textual data
                if symbol and company_name:
                    confidence = 0.6
                if current_price and target_price:
                    confidence = 0.7
                if is_target_growth_range(growth_percent):
                    confidence = min(confidence + 0.15, 1.0)
                
                stock_details = {
                    'symbol': symbol,
                    'company_name': company_name,
                    'entry_price': current_price,
                    'target_price': target_price,
                    'stop_loss': None,  # Not typically provided in text content
                    'growth_percent': growth_percent,
                    'recommendation_type': rec_type,
                    'source': domain,
                    'url': url,
                    'date': datetime.now().strftime('%Y-%m-%d'),
                    'confidence': confidence
                }

                stock_tips.append(stock_details)

    # Deduplicate stock tips
    final_tips = []
    seen_symbols = set()
    
    for tip in stock_tips:
        symbol = tip.get('symbol')
        if symbol and symbol not in seen_symbols:
            final_tips.append(tip)
            seen_symbols.add(symbol)
    
    logger.info(f"Extracted {len(final_tips)} stock tips from Kotak Securities")
    return final_tips

# For testing the module directly
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    )
    
    # Test URL
    test_url = "https://www.kotaksecurities.com/stock-research-recommendations/"
    
    # Fetch HTML
    from base_scraper import fetch_content_with_ab
    html_content = fetch_content_with_ab(test_url)
    
    if html_content:
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract stock tips
        stock_tips = scrape_kotak_securities(soup, test_url)
        
        # Print results
        print(f"\nFound {len(stock_tips)} stock tips from Kotak Securities:")
        for i, tip in enumerate(stock_tips):
            growth_str = f"{tip['growth_percent']}%" if tip['growth_percent'] is not None else "N/A"
            print(f"{i+1}. {tip.get('company_name')} ({tip.get('symbol')}) - Entry: {tip['entry_price']}, Target: {tip['target_price']}, Growth: {growth_str}")
    else:
        print("Failed to fetch content from Kotak Securities")
