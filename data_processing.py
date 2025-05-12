#!/usr/bin/env python3
# data_processing.py - Functions for filtering and processing stock data

import os
import logging
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

def filter_quality_tips(stock_tips, min_confidence=0.7):
    """
    Filter stock tips by quality/confidence score
    
    Args:
        stock_tips (list): List of stock tip dictionaries
        min_confidence (float): Minimum confidence threshold
        
    Returns:
        list: Filtered list of high-quality stock tips
    """
    if not stock_tips:
        return []
    
    quality_tips = [tip for tip in stock_tips if tip.get('confidence', 0) >= min_confidence]
    
    # Sort by confidence (descending)
    quality_tips = sorted(quality_tips, key=lambda x: x.get('confidence', 0), reverse=True)
    
    logger.info(f"Filtered {len(quality_tips)} quality stock tips out of {len(stock_tips)} total tips")
    return quality_tips

def filter_target_growth(stock_tips, min_growth=None, max_growth=None):
    """
    Process stock tips with growth information, no longer filtering by range
    
    Args:
        stock_tips (list): List of stock tip dictionaries
        min_growth (float, optional): Minimum growth percentage (not used, kept for backward compatibility)
        max_growth (float, optional): Maximum growth percentage (not used, kept for backward compatibility)
        
    Returns:
        list: All stock tips sorted by confidence score
    """
    if not stock_tips:
        return []
    
    # Instead of filtering, we'll just sort the tips by confidence level
    # Including all stocks regardless of growth percentage
    processed_tips = [tip for tip in stock_tips if tip.get('growth_percent') is not None]
    
    # Sort by confidence (descending)
    processed_tips = sorted(processed_tips, key=lambda x: x.get('confidence', 0), reverse=True)
    
    logger.info(f"Processed {len(processed_tips)} stock tips with growth information")
    return processed_tips

# Keep the original function name as an alias for backward compatibility
def filter_target_growth_tips(stock_tips, min_growth=7, max_growth=15):
    """Alias for filter_target_growth function"""
    return filter_target_growth(stock_tips, min_growth, max_growth)

def deduplicate_stock_tips(stock_tips):
    """
    Remove duplicate stock tips based on symbol and target price
    
    Args:
        stock_tips (list): List of stock tip dictionaries
        
    Returns:
        list: Deduplicated list of stock tips
    """
    if not stock_tips:
        return []
    
    # Create a signature for each tip
    unique_tips = {}
    for tip in stock_tips:
        symbol = tip.get('symbol')
        company = tip.get('company_name')
        target = tip.get('target_price')
        
        # Create a signature
        if symbol:
            key = f"{symbol}_{target}"
        else:
            key = f"{company}_{target}"
        
        # Keep the tip with the highest confidence if duplicates exist
        if key not in unique_tips or tip.get('confidence', 0) > unique_tips[key].get('confidence', 0):
            unique_tips[key] = tip
    
    # Convert back to list
    deduplicated_tips = list(unique_tips.values())
    
    logger.info(f"Deduplicated {len(stock_tips)} stock tips to {len(deduplicated_tips)} unique tips")
    return deduplicated_tips

def save_stock_tips_to_csv(stock_tips, filename_prefix="stock_tips"):
    """
    Save stock tips to a CSV file with timestamp
    
    Args:
        stock_tips (list): List of stock tip dictionaries
        filename_prefix (str): Prefix for the output filename
        
    Returns:
        str: Path to the saved CSV file or None if save failed
    """
    if not stock_tips:
        logger.warning("No stock tips to save")
        return None
    
    # Create DataFrame
    df = pd.DataFrame(stock_tips)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{filename_prefix}_{timestamp}.csv"
    
    # Save to CSV
    df.to_csv(filename, index=False)
    logger.info(f"Saved {len(stock_tips)} stock tips to {filename}")
    
    return filename

def process_stock_tips(all_stock_tips):
    """
    Process all stock tips and return filtered results
    
    Args:
        all_stock_tips (list): List of all collected stock tips
        
    Returns:
        tuple: (quality_tips, target_growth_tips) - filtered tip lists
    """
    # Deduplicate tips
    unique_tips = deduplicate_stock_tips(all_stock_tips)
    
    # Filter for quality tips
    quality_tips = filter_quality_tips(unique_tips)
    
    # Filter for target growth tips (7-15% range)
    target_growth_tips = filter_target_growth(unique_tips)
    
    # Save results to CSV
    if quality_tips:
        save_stock_tips_to_csv(quality_tips, "quality_stock_tips")
    
    if target_growth_tips:
        save_stock_tips_to_csv(target_growth_tips, "target_growth_stock_tips")
    
    # Save all tips for reference
    if unique_tips:
        save_stock_tips_to_csv(unique_tips, "all_stock_tips")
    
    return quality_tips, target_growth_tips

def consolidate_findings(stock_tips_list):
    """
    Consolidate findings from multiple scraping sources
    
    Args:
        stock_tips_list (list): List of stock tips lists from different sources
        
    Returns:
        list: Consolidated and deduplicated list of stock tips
    """
    # Flatten the list of stock tips if it's a list of lists
    all_tips = []
    for tips in stock_tips_list:
        if isinstance(tips, list):
            all_tips.extend(tips)
        else:
            all_tips.append(tips)
    
    # Deduplicate tips
    unique_tips = deduplicate_stock_tips(all_tips)
    
    # Sort by confidence (descending)
    sorted_tips = sorted(unique_tips, key=lambda x: x.get('confidence', 0), reverse=True)
    
    logger.info(f"Consolidated {len(all_tips)} stock tips from multiple sources into {len(sorted_tips)} unique tips")
    return sorted_tips