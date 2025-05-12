#!/usr/bin/env python3
# test_moneycontrol_bs4.py - Test script for the MoneyControl scraper using BeautifulSoup approach

import os
import json
import logging
import time
from bs4 import BeautifulSoup
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
)
logger = logging.getLogger(__name__)

# Import necessary functions
from base_scraper import fetch_content_with_ab, clean_price, calculate_growth_percent

def parse_moneycontrol_with_bs4(html_content, url):
    """
    Simplified version of the MoneyControl scraper that uses BeautifulSoup only
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    stock_tips = []
    domain = "moneycontrol.com"
    
    try:
        # Extract stock recommendation cards
        recommendation_blocks = soup.select('.InfoCardsSec_web_stckCard__X8CAV')
        logger.info(f"Found {len(recommendation_blocks)} stock recommendation cards in MoneyControl")
        
        # Process each recommendation card
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
                    import re
                    date_match = re.search(r'Reco on : (.+?)$', reco_date_elem.text)
                    if date_match:
                        reco_date = date_match.group(1).strip()
                
                # Extract stock name and symbol
                company_elem = block.select_one('.InfoCardsSec_web_comTitle__cZ083 a')
                if company_elem:
                    company_name = company_elem.text.strip()
                    company_url = company_elem.get('href', '')
                    # Extract symbol from URL
                    import re
                    symbol_match = re.search(r'/([A-Z0-9]{2,8})$', company_url)
                    if symbol_match:
                        symbol = symbol_match.group(1)
                
                # Extract recommendation type (Buy/Sell/Hold)
                if block.select_one('.InfoCardsSec_web_buy__0pluJ'):
                    recommendation_type = 'buy'
                elif block.select_one('.InfoCardsSec_web_sell__RiuGp'):
                    recommendation_type = 'sell'
                elif block.select_one('.InfoCardsSec_web_hold__HVdXo'):
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
                        import re
                        target_match = re.search(r'(\d+(?:,\d+)*(?:\.\d+)?)\s*\(([