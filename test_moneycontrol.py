#!/usr/bin/env python3
# test_moneycontrol.py - Test script for MoneyControl scraper

import os
import sys
import json
import logging
import asyncio
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
)
logger = logging.getLogger(__name__)

# Function to fetch MoneyControl HTML directly
def fetch_moneycontrol():
    url = "https://www.moneycontrol.com/markets/stock-ideas/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text
    except Exception as e:
        logger.error(f"Error fetching MoneyControl: {e}")
        return None

# Extract stock recommendation cards
def extract_stock_tips(html_content):
    from base_scraper import clean_price
    import re
    
    soup = BeautifulSoup(html_content, 'html.parser')
    stock_tips = []
    domain = "moneycontrol.com"
    url = "https://www.moneycontrol.com/markets/stock-ideas/"
    
    # Extract stock recommendation cards
    recommendation_blocks = soup.select('.InfoCardsSec_web_stckCard__X8CAV')
    logger.info(f"Found {len(recommendation_blocks)} stock recommendation cards in MoneyControl")
    
    for block in recommendation_blocks:
        try:
            # Initialize variables
            symbol = None
            company_name = None
            entry_price = None
            target_price = None
            recommendation_type = None
            growth_percent = None
                           
            # Extract recommendation date
            reco_date_elem = block.select_one('.InfoCardsSec_web_recoTxt___V6m0')
            reco_date = None
            if reco_date_elem:
                date_match = re.search(r'Reco on : (.+?)$', reco_date_elem.text)
                if date_match:
                    reco_date = date_match.group(1).strip()
            
            # Extract stock name and symbol
            company_elem = block.select_one('.InfoCardsSec_web_comTitle__cZ083 a')
            if company_elem:
                company_name = company_elem.text.strip()
                company_url = company_elem.get('href', '')
                # Extract symbol from URL
                symbol_match = re.search(r'/([A-Z0-9]{2,8})$', company_url)
                if symbol_match:
                    symbol = symbol_match.group(1)
            
            # Extract recommendation type (Buy/Sell/Hold)
            buy_elem = block.select_one('.InfoCardsSec_web_buy__0pluJ')
            sell_elem = block.select_one('.InfoCardsSec_web_sell__RiuGp')
            hold_elem = block.select_one('.InfoCardsSec_web_hold__HVdXo')
            
            if buy_elem:
                recommendation_type = 'buy'
            elif sell_elem:
                recommendation_type = 'sell'
            elif hold_elem:
                recommendation_type = 'hold'
            else:
                recommendation_type = 'buy'  # Default to buy
            
            # Extract price information from table
            price_table = block.select_one('.InfoCardsSec_web_dnTAble__XQgQl')
            if price_table:
                # Extract recommendation price
                reco_price_elem = price_table.select_one('li:nth-child(1) span')
                if reco_price_elem:
                    entry_price = clean_price(reco_price_elem.text.strip())
                
                # Extract target price
                target_elem = price_table.select_one('li:nth-child(2) span')
                if target_elem:
                    # Extract the target price and growth percentage
                    target_text = target_elem.text.strip()
                    target_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)\s*\(([+-]?\d+(?:\.\d+)?)%\)', target_text)
                    
                    if target_match:
                        target_price = clean_price(target_match.group(1))
                        growth_percent = float(target_match.group(2))
                    else:
                        # Try simpler pattern
                        target_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)', target_text)
                        if target_match:
                            target_price = clean_price(target_match.group(1))
                
                # Extract returns
                returns_elem = price_table.select_one('li:nth-child(3) span')
                if returns_elem:
                    returns_text = returns_elem.text.strip()
                    # We don't use this currently but might be useful in future
            
            # Extract PDF research link if available
            pdf_elem = block.select_one('a.InfoCardsSec_web_pdfBtn__LQ71I')
            research_url = None
            research_by = None
            if pdf_elem:
                research_url = pdf_elem.get('href', '')
                research_by_elem = pdf_elem.select_one('p')
                if research_by_elem:
                    research_by = research_by_elem.text.replace('Research by', '').strip()
            
            # Calculate growth percentage if not already found
            if entry_price and target_price and entry_price > 0 and not growth_percent:
                from base_scraper import calculate_growth_percent
                growth_percent = calculate_growth_percent(entry_price, target_price)
                growth_percent = round(growth_percent, 2) if growth_percent is not None else None
            
            # Create stock details if we have enough info
            if (symbol or company_name) and (entry_price or target_price):
                # Calculate confidence based on data completeness
                confidence = 0.7  # Base level
                if symbol:
                    confidence = max(confidence, 0.75)
                if entry_price and target_price:
                    confidence = max(confidence, 0.85)
                if research_url:
                    confidence = max(confidence, 0.9)  # Higher confidence if research PDF available
                
                stock_details = {
                    'symbol': symbol,
                    'company_name': company_name,
                    'entry_price': entry_price,
                    'target_price': target_price,
                    'growth_percent': growth_percent,
                    'recommendation_type': recommendation_type,
                    'source': domain,
                    'url': url,
                    'research_url': research_url,
                    'research_by': research_by,
                    'recommendation_date': reco_date,
                    'date_extracted': datetime.now().strftime('%Y-%m-%d'),
                    'confidence': confidence
                }
                
                stock_tips.append(stock_details)
        except Exception as e:
            logger.error(f"Error processing recommendation block: {e}", exc_info=True)
    
    return stock_tips

def main():
    logger.info("Starting MoneyControl test...")
    
    # Fetch HTML content
    html_content = fetch_moneycontrol()
    
    if not html_content:
        logger.error("Failed to fetch HTML content")
        return
    
    # Save HTML for debugging
    with open("moneycontrol_debug.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info("Saved HTML content to moneycontrol_debug.html")
    
    # Extract stock tips
    stock_tips = extract_stock_tips(html_content)
    
    # Print results
    print(f"\nFound {len(stock_tips)} stock tips from MoneyControl:")
    for i, tip in enumerate(stock_tips[:5]):  # Print first 5 tips
        symbol = tip.get('symbol', 'N/A')
        company = tip.get('company_name', 'N/A')
        entry = tip.get('entry_price', 'N/A')
        target = tip.get('target_price', 'N/A')
        growth = tip.get('growth_percent', 'N/A')
        growth_str = f"{growth}%" if growth is not None else 'N/A'
        rec_type = tip.get('recommendation_type', 'N/A')
        
        print(f"{i+1}. {company} ({symbol})")
        print(f"   {rec_type.upper()} - Entry: {entry}, Target: {target}, Growth: {growth_str}")
        if tip.get('research_by'):
            print(f"   Research by: {tip.get('research_by')}")
        print("")
    
    # Save results to JSON
    if stock_tips:
        output_file = "moneycontrol_test_results.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(stock_tips, f, indent=2)
        
        print(f"\nFull results saved to {output_file}")

if __name__ == "__main__":
    main()
