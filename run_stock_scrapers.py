#!/usr/bin/env python3
# run_stock_scrapers.py - Main script to run stock scrapers for target websites

import os
import json
import logging
import time
import pandas as pd
from datetime import datetime
from bs4 import BeautifulSoup

# Import core modules
from base_scraper import fetch_content_with_ab
from data_processing import filter_target_growth, deduplicate_stock_tips

# Import scrapers module to access all website scrapers
from scrapers import get_scraper, get_url, TARGET_SOURCES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler("stock_scraper.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def scrape_website(source_name):
    """
    Scrape a specific website for stock recommendations
    
    Args:
        source_name (str): Name identifier for the website source
        
    Returns:
        list: List of stock tips or empty list if scraping failed
    """
    logger.info(f"Starting scrape for {source_name}")
    
    # Get the scraper function and URL for this source
    scraper_func = get_scraper(source_name)
    url = get_url(source_name)
    
    if not scraper_func:
        logger.error(f"No scraper function found for {source_name}")
        return []
    
    if not url:
        logger.error(f"No URL found for {source_name}")
        return []
    
    # Fetch the HTML content
    start_time = time.time()
    html_content = fetch_content_with_ab(url)
    fetch_time = time.time() - start_time
    
    if not html_content:
        logger.error(f"Failed to fetch HTML content from {url}")
        return []
    
    logger.info(f"Successfully fetched HTML content from {url} in {fetch_time:.2f} seconds")
    
    # Save HTML content for debugging if needed
    debug_dir = "debug_html"
    os.makedirs(debug_dir, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    debug_html_path = f"{debug_dir}/{source_name}_{timestamp}.html"
    
    try:
        with open(debug_html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        logger.debug(f"Saved HTML content to {debug_html_path}")
    except Exception as e:
        logger.warning(f"Failed to save HTML content: {e}")
    
    # Parse HTML content
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Execute the scraper
    start_time = time.time()
    try:
        stock_tips = scraper_func(soup, url)
        scrape_time = time.time() - start_time
        logger.info(f"Successfully scraped {len(stock_tips)} stock tips from {source_name} in {scrape_time:.2f} seconds")
        return stock_tips
    except Exception as e:
        logger.error(f"Error executing scraper for {source_name}: {e}", exc_info=True)
        return []

def save_results(stock_tips, filename, output_dir):
    """
    Save stock tips to CSV and JSON files
    
    Args:
        stock_tips (list): List of stock tip dictionaries
        filename (str): Base filename without extension
        output_dir (str): Directory to save files
        
    Returns:
        tuple: Paths to the saved files (json_path, csv_path)
    """
    if not stock_tips:
        logger.warning(f"No stock tips to save for {filename}")
        return None, None
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Define file paths
    json_path = os.path.join(output_dir, f"{filename}.json")
    csv_path = os.path.join(output_dir, f"{filename}.csv")
    
    # Save as JSON
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(stock_tips, f, indent=2)
        logger.info(f"Saved JSON results to {json_path}")
    except Exception as e:
        logger.error(f"Error saving JSON results: {e}")
        json_path = None
    
    # Save as CSV
    try:
        df = pd.DataFrame(stock_tips)
        df.to_csv(csv_path, index=False)
        logger.info(f"Saved CSV results to {csv_path}")
    except Exception as e:
        logger.error(f"Error saving CSV results: {e}")
        csv_path = None
    
    return json_path, csv_path

def create_summary_report(results, output_dir):
    """
    Create a summary report of scraping results
    
    Args:
        results (dict): Dictionary mapping source names to their stock tips
        output_dir (str): Directory to save the report
        
    Returns:
        str: Path to the summary report
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate summary report filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = os.path.join(output_dir, f"summary_report_{timestamp}.md")
    
    # Calculate stats
    total_sources = len(results)
    successful_sources = sum(1 for tips in results.values() if tips)
    total_tips = sum(len(tips) for tips in results.values() if tips)
    
    # Combine all tips
    all_tips = []
    for source_tips in results.values():
        if source_tips:
            all_tips.extend(source_tips)
    
    # Get target growth tips
    target_growth_tips = filter_target_growth(all_tips)
    
    # Create report content
    report_content = f"""# Stock Scraper Summary Report

## Overview
- **Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
- **Total Websites Scraped:** {total_sources}
- **Successfully Scraped Websites:** {successful_sources}
- **Total Stock Tips Found:** {total_tips}
- **Stock Tips in Target Growth Range (7-15%):** {len(target_growth_tips)}

## Details by Source

"""
    
    # Add details for each source
    for source_name, tips in results.items():
        tip_count = len(tips) if tips else 0
        target_growth_count = len(filter_target_growth(tips)) if tips else 0
        
        # Get the URL for this source
        url = get_url(source_name)
        
        report_content += f"### {source_name}\n"
        report_content += f"- **URL:** {url}\n"
        report_content += f"- **Total Tips:** {tip_count}\n"
        report_content += f"- **Tips in Target Range:** {target_growth_count}\n"
        
        # Include sample tips if available
        if tips and tip_count > 0:
            report_content += "- **Sample Tips:**\n"
            
            # Sort by confidence
            sorted_tips = sorted(tips, key=lambda x: x.get('confidence', 0), reverse=True)
            
            for i, tip in enumerate(sorted_tips[:3]):  # Show top 3 tips
                symbol = tip.get('symbol', 'N/A')
                company = tip.get('company_name', 'N/A')
                entry = tip.get('entry_price', 'N/A')
                target = tip.get('target_price', 'N/A')
                growth = tip.get('growth_percent', 'N/A')
                growth_str = f"{growth}%" if growth is not None else 'N/A'
                
                report_content += f"  {i+1}. **{symbol}** ({company}): Entry ₹{entry}, Target ₹{target}, Growth {growth_str}\n"
        
        report_content += "\n"
    
    # Add section for target growth tips
    if target_growth_tips:
        report_content += f"## Top Tips in Target Growth Range (7-15%)\n\n"
        report_content += "| Symbol | Company | Entry Price | Target Price | Growth % | Source |\n"
        report_content += "|--------|---------|-------------|--------------|----------|--------|\n"
        
        # Sort by confidence
        sorted_tips = sorted(target_growth_tips, 
                           key=lambda x: (x.get('confidence', 0), x.get('growth_percent', 0)), 
                           reverse=True)
        
        for tip in sorted_tips[:10]:  # Top 10 tips
            symbol = tip.get('symbol', 'N/A')
            company = tip.get('company_name', 'N/A')
            entry = tip.get('entry_price', 'N/A')
            target = tip.get('target_price', 'N/A')
            growth = tip.get('growth_percent', 'N/A')
            growth_str = f"{growth}%" if growth is not None else 'N/A'
            source = tip.get('source', 'N/A')
            
            report_content += f"| {symbol} | {company} | ₹{entry} | ₹{target} | {growth_str} | {source} |\n"
    
    # Save the report
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_content)
        logger.info(f"Created summary report at {report_path}")
    except Exception as e:
        logger.error(f"Error creating summary report: {e}")
        report_path = None
    
    return report_path

def print_summary(results):
    """
    Print a summary of the scraping results to the console
    
    Args:
        results (dict): Dictionary mapping source names to their stock tips
    """
    print("\n" + "="*60)
    print("STOCK SCRAPER SUMMARY")
    print("="*60)
    
    # Calculate stats
    total_sources = len(results)
    successful_sources = sum(1 for tips in results.values() if tips)
    total_tips = sum(len(tips) for tips in results.values() if tips)
    
    print(f"Websites Scraped: {successful_sources}/{total_sources}")
    print(f"Total Stock Tips Found: {total_tips}")
    
    # Print results by source
    print("\nResults by Source:")
    for source, tips in results.items():
        tip_count = len(tips) if tips else 0
        print(f"- {source}: {tip_count} tips")
    
    # Combine all tips
    all_tips = []
    for source_tips in results.values():
        if source_tips:
            all_tips.extend(source_tips)
    
    # Print target growth info
    target_growth_tips = filter_target_growth(all_tips)
    print(f"\nStock Tips in Target Growth Range (7-15%): {len(target_growth_tips)}")
    
    # Print top tips
    if target_growth_tips:
        print("\nTop Tips in Target Range:")
        sorted_tips = sorted(target_growth_tips, 
                           key=lambda x: (x.get('confidence', 0), x.get('growth_percent', 0)), 
                           reverse=True)
        
        for i, tip in enumerate(sorted_tips[:5]):
            symbol = tip.get('symbol', 'N/A')
            company = tip.get('company_name', 'N/A')
            if company and len(company) > 30:
                company = company[:27] + "..."
            entry = tip.get('entry_price', 'N/A')
            target = tip.get('target_price', 'N/A')
            growth = tip.get('growth_percent', 'N/A')
            growth_str = f"{growth}%" if growth is not None else 'N/A'
            source = tip.get('source', 'N/A')
            
            print(f"  {i+1}. {symbol} ({company}) - Entry: ₹{entry}, Target: ₹{target}, Growth: {growth_str}, Source: {source}")
    
    print("="*60)

def run_scrapers(sources=None, output_base_dir="output"):
    """
    Run scrapers for specified sources and save results
    
    Args:
        sources (list): List of source names to scrape, or None for all sources
        output_base_dir (str): Base directory for output files
        
    Returns:
        tuple: (output_dir, results) where results is a dict mapping sources to stock tips
    """
    # Use all sources if none specified
    if sources is None:
        sources = TARGET_SOURCES
    
    # Create output directory with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = os.path.join(output_base_dir, f"output_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)
    
    # Dictionary to store results
    results = {}
    
    # Process each source
    for source_name in sources:
        logger.info(f"Processing {source_name}")
        
        # Scrape the website
        stock_tips = scrape_website(source_name)
        
        # Store results
        results[source_name] = stock_tips
        
        # Save individual results if any tips found
        if stock_tips:
            save_results(stock_tips, source_name, output_dir)
        
        # Add a small delay between requests
        time.sleep(2)
    
    # Combine all results
    all_stock_tips = []
    for source_tips in results.values():
        if source_tips:
            all_stock_tips.extend(source_tips)
    
    # Deduplicate combined results
    all_stock_tips = deduplicate_stock_tips(all_stock_tips)
    
    # Save combined results
    if all_stock_tips:
        save_results(all_stock_tips, "all_sources", output_dir)
        
        # Generate and save target growth results
        target_growth_tips = filter_target_growth(all_stock_tips)
        if target_growth_tips:
            save_results(target_growth_tips, "target_growth", output_dir)
    
    # Create summary report
    create_summary_report(results, output_dir)
    
    return output_dir, results

if __name__ == "__main__":
    # Set up command line argument parsing
    import argparse
    
    parser = argparse.ArgumentParser(description="Run stock scrapers for target financial websites")
    parser.add_argument("--sources", nargs="+", choices=TARGET_SOURCES, help="Specific sources to scrape")
    parser.add_argument("--output-dir", default="output", help="Base directory for output files")
    
    args = parser.parse_args()
    
    # Run the scrapers
    logger.info("Starting stock scraper")
    output_dir, results = run_scrapers(args.sources, args.output_dir)
    
    # Print summary
    print_summary(results)
    
    # Print output location
    print(f"\nResults saved to: {output_dir}")
