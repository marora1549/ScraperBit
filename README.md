# ScraperBit

A specialized stock leads scraper system that extracts potential investment opportunities from financial websites, focusing on stocks with 7-15% growth potential.

## Project Overview

ScraperBit is a modular Python-based web scraping system designed to extract stock recommendations from various financial websites. The system identifies potential investment opportunities, particularly focusing on stocks with 7-15% growth potential, by parsing stock recommendations across multiple sources.

### Key Features

- **Modular Architecture**: Each website has its own specialized scraper
- **Anti-Blocking Measures**: Implements techniques to avoid being blocked by websites
- **Data Processing**: Cleans and standardizes extracted data
- **Growth Potential Focus**: Targets stocks with 7-15% growth potential
- **Comprehensive Reporting**: Generates detailed reports on findings

## Project Structure

- `base_scraper.py` - Core scraping functionality and utility functions
- `anti_blocking.py` - Anti-scraping prevention measures
- `data_processing.py` - Data cleaning and processing functions
- `scrapers/` - Directory containing website-specific scrapers
- `run_target_websites.py` - Main script to run scrapers for target websites

## Supported Websites

- Axis Direct
- ICICI Direct
- Kotak Securities
- 5paisa
- Sharekhan
- MoneyControl

## Getting Started

### Prerequisites

- Python 3.7+
- Required packages listed in `requirements.txt`

### Installation

1. Clone the repository:
```bash
git clone https://github.com/marora1549/ScraperBit.git
cd ScraperBit
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

### Usage

Run the main script to scrape all target websites:

```bash
python run_target_websites.py
```

For testing individual scrapers:

```bash
python test_scraper.py [source_name] [url]
```

## Project Development Status

Please refer to the following files for detailed project status:
- `planning.md` - Project planning and architecture
- `tasks.md` - Current tasks and progress tracking

## License

[MIT License](LICENSE)
