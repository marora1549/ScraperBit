#!/usr/bin/env python3
# base_scraper.py - Core scraping functionality and utility functions

import json
import time
import logging
import random
import os
import re
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor

from anti_blocking import AntiBlockingManager  # Import AntiBlockingManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler("stock_leads.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize AntiBlockingManager
ab_manager = AntiBlockingManager(use_rotating_agents=True, use_random_delays=True)

# --- Utility Functions ---
def clean_text(text):
    """Clean and normalize text content"""
    if not text:
        return ""
    # Replace new lines with space
    text = re.sub(r'\n+', ' ', text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters
    text = re.sub(r'[^\w\s\.\,\:\;\-\₹\$\%\(\)]', ' ', text)
    return text.strip()

def clean_price(price_str):
    """Clean price string and convert to float"""
    if price_str is None:
        return None
    if isinstance(price_str, str) and price_str.strip().upper() in ['NA', 'N/A', '-']:
        return None
    try:
        # Remove rupee symbols, commas and other non-numeric characters
        cleaned = re.sub(r'[^\d.]', '', str(price_str))
        return float(cleaned) if cleaned else None
    except:
        logging.warning(f"Could not clean/convert price: '{price_str}'")
        return None

def calculate_growth_percent(entry_price, target_price):
    """Calculate growth percentage"""
    if not entry_price or not target_price or entry_price <= 0:
        return None
    return ((target_price - entry_price) / entry_price) * 100

def is_target_growth_range(growth_percent, min_growth=7, max_growth=15):
    """Check if the growth percentage is within the target range"""
    if growth_percent is None:
        return False
    return min_growth <= growth_percent <= max_growth

# --- Web Scraping Functions ---
def fetch_content_with_ab(url, timeout=30, retries=2):
    """Fetch content from a URL using AntiBlockingManager"""
    logger.debug(f"Fetching {url} using AntiBlockingManager")
    success, content, status_code = ab_manager.fetch_with_anti_blocking(url, retries=retries, timeout=timeout)
    if success:
        return content
    else:
        logger.error(f"Failed to fetch {url} after {retries} retries with AntiBlockingManager. Status: {status_code}, Error: {content}")
        return None

def fetch_with_playwright_sync(url, timeout=30000):
    """
    Synchronous wrapper for fetching a URL using Playwright
    
    Args:
        url (str): URL to scrape
        timeout (int): Timeout in milliseconds
        
    Returns:
        str: HTML content or None if failed
    """
    try:
        import asyncio
        from playwright.async_api import async_playwright
        
        async def _fetch_content():
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
                    
                    # Get the HTML content
                    html_content = await page.content()
                    
                    # Close the browser
                    await browser.close()
            except Exception as e:
                logger.error(f"Error fetching with Playwright: {e}", exc_info=True)
            
            return html_content
        
        # Run the async function using the event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        html_content = loop.run_until_complete(_fetch_content())
        return html_content
    
    except ImportError:
        logger.error("Playwright is not installed. Please install it with 'pip install playwright' and run 'playwright install'")
        return None
    except Exception as e:
        logger.error(f"Error in fetch_with_playwright_sync: {e}", exc_info=True)
        return None

def extract_stock_details(text, source_url=None):
    """Extract stock details from text using advanced pattern matching"""
    result = {
        'symbol': None,
        'company_name': None,
        'entry_price': None,
        'target_price': None,
        'stop_loss': None,
        'growth_percent': None,
        'recommendation_type': None,
        'source': urlparse(source_url).netloc if source_url else None,
        'url': source_url,
        'date': datetime.now().strftime('%Y-%m-%d'),
        'raw_text': text[:500] + '...' if len(text) > 500 else text,
        'confidence': 0.5,  # Default confidence
    }
    
    # Clean and normalize text
    text_cleaned = clean_text(text)  # Use a different variable name to avoid confusion with original text for raw_text
    text_lower = text_cleaned.lower()
    
    # Extract stock symbol - using common Indian stock notation
    symbol_patterns = [
        r'\b([A-Z]{2,5})\b(?:\s*(?:NSE|BSE))?',  # Basic stock symbols like RELIANCE, INFY, TCS
        r'\b([A-Z]{2,5}[0-9]{1,2})\b',           # Symbols with numbers like IDEA2, BHEL5
        r'NSE[:/]([A-Z]{2,5})\b',                # NSE:SYMBOL format
        r'BSE[:/]([A-Z]{2,5})\b',                # BSE:SYMBOL format
        r'(?:stock|ticker|symbol)[:\s]+([A-Z]{2,5})',  # Named symbol
    ]
    
    # Try to find stock symbols
    for pattern in symbol_patterns:
        symbol_matches = re.findall(pattern, text_cleaned)  # Use cleaned text
        filtered_symbols = [s for s in symbol_matches if isinstance(s, str) and s not in ['NSE', 'BSE', 'BUY', 'SELL', 'CMP', 'HOLD', 'SL', 'TGT', 'MRP', 'INR', 'THE', 'FOR', 'LTD']]
        
        if filtered_symbols:
            result['symbol'] = filtered_symbols[0]
            break
    
    # Try to extract company name
    if not result['symbol']:
        # If no symbol found, look for company name with 'Ltd' or similar
        company_patterns = [
            r'([A-Z][a-zA-Z\s]+(?:Ltd|Limited|Corp|Corporation|Pvt|Private|Inc|Incorporated))',
            r'([A-Z][a-zA-Z\s]{3,})\s+(?:shares|stock)',
        ]
        for pattern in company_patterns:
            company_matches = re.findall(pattern, text_cleaned)
            if company_matches:
                result['company_name'] = company_matches[0].strip()
                break
    
    # If no specific company name found, use a general approach to find capitalized words
    if not result['company_name'] and not result['symbol']:
        # Look for names with proper capitalization (3+ words)
        capital_matches = re.findall(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){2,})', text_cleaned)
        if capital_matches:
            result['company_name'] = capital_matches[0].strip()
    
    # Find current price (CMP)
    cmp_patterns = [
        r'(?:CMP|current\s+market\s+price|current\s+price|trading\s+at|price)[:\s]*(?:Rs\.?|₹)?\s*([0-9,.]+)',
        r'(?:Rs\.?|₹)\s*([0-9,.]+)\s*(?:CMP|current|\bat\b)',
        r'(?:stock|share)\s+(?:is|was)\s+(?:trading|priced)\s+at\s+(?:Rs\.?|₹)?\s*([0-9,.]+)',
    ]
    
    for pattern in cmp_patterns:
        cmp_matches = re.findall(pattern, text_lower)
        if cmp_matches:
            result['entry_price'] = clean_price(cmp_matches[0])
            break
    
    # Find target price
    target_patterns = [
        r'(?:target|price target|target price|tp)[:\s]*(?:Rs\.?|₹)?\s*([0-9,.]+)',
        r'(?:Rs\.?|₹)\s*([0-9,.]+)\s*(?:target|price target)',
        r'(?:upside|increase) to\s+(?:Rs\.?|₹)?\s*([0-9,.]+)',
    ]
    
    for pattern in target_patterns:
        target_matches = re.findall(pattern, text_lower)
        if target_matches:
            result['target_price'] = clean_price(target_matches[0])
            # Since we have a target, let's increase the confidence
            result['confidence'] = max(result['confidence'], 0.6)
            break
    
    # Find stop loss price
    sl_patterns = [
        r'(?:stop\s*loss|sl)[:\s]*(?:Rs\.?|₹)?\s*([0-9,.]+)',
        r'(?:Rs\.?|₹)\s*([0-9,.]+)\s*(?:stop\s*loss|sl)',
    ]
    
    for pattern in sl_patterns:
        sl_matches = re.findall(pattern, text_lower)
        if sl_matches:
            result['stop_loss'] = clean_price(sl_matches[0])
            # Having a stop loss increases confidence
            result['confidence'] = max(result['confidence'], 0.65)
            break
    
    # Determine recommendation type
    rec_type = None
    if 'buy' in text_lower or 'bullish' in text_lower or 'accumulate' in text_lower:
        rec_type = 'buy'
        # If explicitly marked as buy, higher confidence
        result['confidence'] = max(result['confidence'], 0.7)
    elif 'sell' in text_lower or 'bearish' in text_lower or 'reduce' in text_lower:
        rec_type = 'sell'
        # If explicitly marked as sell, higher confidence
        result['confidence'] = max(result['confidence'], 0.7)
    elif 'hold' in text_lower or 'neutral' in text_lower:
        rec_type = 'hold'
        # If explicitly marked as hold, higher confidence
        result['confidence'] = max(result['confidence'], 0.7)
    else:
        # Default to buy as many recommendations are implicit buys
        rec_type = 'buy'
    
    result['recommendation_type'] = rec_type
    
    # Calculate growth percentage if we have both entry and target prices
    if result['entry_price'] and result['target_price'] and result['entry_price'] > 0:
        result['growth_percent'] = calculate_growth_percent(result['entry_price'], result['target_price'])
        result['growth_percent'] = round(result['growth_percent'], 2) if result['growth_percent'] is not None else None
        
        # If growth percentage is in target range, increase confidence
        if is_target_growth_range(result['growth_percent']):
            result['confidence'] = min(result['confidence'] + 0.15, 1.0)
    
    return result

def scrape_website(url):
    """Scrape a website for stock tips"""
    logger.info(f"Scraping website: {url}")
    stock_tips = []
    
    try:
        # Fetch content
        html_content = fetch_content_with_ab(url)
        if not html_content:
            logger.error(f"Failed to fetch content from {url}")
            return []
            
        from complete_stock_finder import extract_stock_tips_from_page
        # Extract stock tips using the appropriate scraper
        stock_tips = extract_stock_tips_from_page(html_content, url)
        
        logger.info(f"Extracted {len(stock_tips)} stock tips from {url}")
        return stock_tips
    except Exception as e:
        logger.error(f"Error scraping {url}: {e}", exc_info=True)
        return []

def scrape_multi_threaded(urls_to_scrape, max_workers=5):
    """Scrape multiple websites concurrently"""
    logger.info(f"Starting multi-threaded scraping of {len(urls_to_scrape)} websites with {max_workers} workers")
    all_stock_tips = []
    
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit scraping tasks
            future_to_url = {executor.submit(scrape_website, url): url for url in urls_to_scrape}
            
            # Process results as they complete
            for future in future_to_url:
                url = future_to_url[future]
                try:
                    stock_tips = future.result()
                    all_stock_tips.extend(stock_tips)
                    logger.info(f"Successfully scraped {url} - found {len(stock_tips)} stock tips")
                except Exception as e:
                    logger.error(f"Error processing results from {url}: {e}", exc_info=True)
    
    except Exception as e:
        logger.error(f"Error in multi-threaded scraping: {e}", exc_info=True)
    
    logger.info(f"Multi-threaded scraping completed. Total stock tips: {len(all_stock_tips)}")
    return all_stock_tips