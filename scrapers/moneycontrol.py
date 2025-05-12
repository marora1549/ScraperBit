#!/usr/bin/env python3
# moneycontrol.py - Specialized scraper for MoneyControl using Playwright

import re
import json
import logging
import asyncio
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from datetime import datetime
from playwright.async_api import async_playwright

from base_scraper import clean_price, calculate_growth_percent, is_target_growth_range

logger = logging.getLogger(__name__)

async def fetch_with_playwright(url, timeout=30000):
    """
    Fetch a URL using Playwright with proper handling of JavaScript-loaded content
    
    Args:
        url (str): URL to scrape
        timeout (int): Timeout in milliseconds
        
    Returns:
        str: HTML content or None if failed
    """
    html_content = None
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36"
            )
            
            # Create a new page
            page = await context.new_page()
            
            # Navigate to the URL
            await page.goto(url, wait_until="networkidle", timeout=timeout)
            
            # Wait for stock recommendation cards to load
            try:
                await page.wait_for_selector('.InfoCardsSec_web_stckCard__X8CAV', timeout=10000)
            except:
                logger.warning("Timed out waiting for stock cards to load. Will attempt to parse what's available.")
            
            # Get the HTML content
            html_content = await page.content()
            
            # Close the browser
            await browser.close()
    
    except Exception as e:
        logger.error(f"Error fetching with Playwright: {e}", exc_info=True)
    
    return html_content

def scrape_moneycontrol(soup, url):
    """
    Specialized scraper for MoneyControl website
    
    Args:
        soup (BeautifulSoup): Parsed HTML content
        url (str): URL of the page being scraped
        
    Returns:
        list: List of stock tips extracted from the page
    """
    # For static use - if soup is provided, use it
    # For real usage, the run_stock_scrapers.py will call the async version
    stock_tips = []
    domain = "moneycontrol.com"
    
    try:
        # Extract stock recommendation cards using the structure observed in the HTML
        recommendation_blocks = soup.select('.InfoCardsSec_web_stckCard__X8CAV')
        
        logger.info(f"Found {len(recommendation_blocks)} stock recommendation cards in MoneyControl")
        
        for block in recommendation_blocks:
            try:
                # Initialize variables
                symbol = None
                company_name = None
                entry_price = None
                target_price = None
                stop_loss = None
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
                logger.error(f"Error processing MoneyControl recommendation block: {e}", exc_info=True)
    
    except Exception as e:
        logger.error(f"Error processing MoneyControl page: {e}", exc_info=True)
    
    # Deduplicate based on symbol
    final_tips = []
    seen_symbols = set()
    
    # Sort by confidence (highest first)
    sorted_tips = sorted(stock_tips, key=lambda x: (x.get('confidence', 0)), reverse=True)
    
    for tip in sorted_tips:
        symbol = tip.get('symbol')
        if symbol and symbol not in seen_symbols:
            final_tips.append(tip)
            seen_symbols.add(symbol)
        elif not symbol and tip.get('company_name') and tip not in final_tips:
            # If no symbol but has company name, use company name for deduplication
            if not any(t.get('company_name') == tip.get('company_name') for t in final_tips):
                final_tips.append(tip)
    
    logger.info(f"Extracted {len(final_tips)} stock tips from MoneyControl")
    return final_tips

async def fetch_and_scrape_moneycontrol(url):
    """
    Fetch and scrape MoneyControl website using Playwright
    
    Args:
        url (str): URL to scrape
        
    Returns:
        list: List of stock tips
    """
    html_content = await fetch_with_playwright(url)
    
    if not html_content:
        logger.error(f"Failed to fetch HTML content from {url}")
        return []
    
    soup = BeautifulSoup(html_content, 'html.parser')
    stock_tips = scrape_moneycontrol(soup, url)
    
    return stock_tips

def run_moneycontrol_scraper(url):
    """
    Run the MoneyControl scraper as a standalone function
    
    Args:
        url (str): URL to scrape
        
    Returns:
        list: List of stock tips
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    stock_tips = loop.run_until_complete(fetch_and_scrape_moneycontrol(url))
    return stock_tips

# For testing the module directly
if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    )
    
    # Test URL
    test_url = "https://www.moneycontrol.com/markets/stock-ideas/"
    
    # Run the scraper
    stock_tips = run_moneycontrol_scraper(test_url)
    
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
        print(f"   Entry: {entry}, Target: {target}, Growth: {growth_str}")
        print(f"   Recommendation: {rec_type}")
        print("")
    
    # Save results to JSON
    if stock_tips:
        with open("moneycontrol_test_results.json", "w", encoding="utf-8") as f:
            json.dump(stock_tips, f, indent=2)
