# ScraperBit

A specialized stock leads scraper system that extracts potential investment opportunities from financial websites.

## Project Overview

ScraperBit is a modular Python-based web scraping system designed to extract stock recommendations from various financial websites. The system identifies potential investment opportunities by parsing stock recommendations across multiple sources, providing consolidated data in a consistent JSON format.

### Key Features

- **Modular Architecture**: Each website has its own specialized scraper
- **Anti-Blocking Measures**: Implements techniques to avoid being blocked by websites
- **Dynamic Content Handling**: Uses Playwright for JavaScript-rendered content
- **Data Processing**: Cleans and standardizes extracted data
- **Comprehensive Reporting**: Generates detailed reports on findings
- **JSON API-Ready Output**: Structured for easy integration with APIs

## Project Structure

- `base_scraper.py` - Core scraping functionality and utility functions
- `anti_blocking.py` - Anti-scraping prevention measures
- `data_processing.py` - Data cleaning and processing functions
- `scrapers/` - Directory containing website-specific scrapers
- `run_stock_scrapers.py` - Main script to run scrapers for target websites

## Supported Websites

- Axis Direct
- ICICI Direct
- 5paisa
- MoneyControl

## Getting Started

### Prerequisites

- Python 3.7+
- Required packages listed in `requirements.txt`
- Playwright (for MoneyControl scraper)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ScraperBit.git
cd ScraperBit
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright (required for MoneyControl scraper):
```bash
playwright install
```

### Usage

Run the main script to scrape all target websites:

```bash
python run_stock_scrapers.py
```

To scrape specific websites only:

```bash
python run_stock_scrapers.py --sources axis_direct icici_direct moneycontrol
```

To specify a custom output directory:

```bash
python run_stock_scrapers.py --output-dir ./custom_output
```

## Development Notes

### MoneyControl Scraper

The MoneyControl scraper uses Playwright to handle JavaScript-rendered content. This approach provides several advantages:
- Properly renders dynamic content loaded via JavaScript
- Can handle complex UI interactions
- Waits for elements to be fully loaded before scraping

If Playwright is not available, the system will fall back to a simplified scraping approach, but results may be limited.

### JSON Output Format

All stock tips are saved in a structured JSON format with the following fields:
- `symbol`: Stock symbol/ticker
- `company_name`: Full company name
- `entry_price`: Recommended entry price
- `target_price`: Target price
- `growth_percent`: Calculated growth percentage
- `recommendation_type`: Buy/Sell/Hold recommendation
- `source`: Source website
- `url`: URL of the recommendation
- `date_extracted`: Date when the data was extracted
- `confidence`: Confidence score (0-1) based on data completeness

## Project Development Status

Please refer to the following files for detailed project status:
- `planning.md` - Project planning and architecture
- `tasks.md` - Current tasks and progress tracking

## License

[MIT License](LICENSE)
