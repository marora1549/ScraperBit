# ScraperBit Project Planning

## Project Overview
ScraperBit is a stock tip scraper that extracts investment recommendations from various financial websites. The project currently scrapes 6 websites, with 3 working successfully (Axis Direct, ICICI Direct, and 5Paisa).

## Requirements
Based on client requirements, we need to:

1. **Retain Working Scrapers:**
   - Axis Direct
   - ICICI Direct 
   - 5Paisa

2. **Remove Non-Essential Scrapers:**
   - Kotak Securities
   - Sharekhan

3. **Fix MoneyControl Scraper:**
   - Implement or fix the MoneyControl scraper to extract stock tips successfully

4. **Remove Growth Range Filter:**
   - Remove the 7-15% profit range filter to display all stock recommendations

5. **Keep JSON Output Format Only:**
   - The output should only use JSON format since this will eventually be used as an API endpoint

## Technical Approach

### Code Structure Modifications
1. Update the `scrapers/__init__.py` file to remove the dropped scrapers
2. Fix the MoneyControl scraper implementation
3. Modify the data processing module to remove the growth range filter
4. Update the main scraper runner to maintain only JSON output

### Testing Approach
1. Test each scraper independently to verify functionality
2. Test the end-to-end flow to ensure all components work together correctly

### Output Format
Focus on a clean, consistent JSON structure for all outputs, removing CSV and other formats.

## Timeline
1. Environment setup and code analysis (Complete)
2. Implementation of required changes
3. Testing and validation
4. Documentation and delivery
