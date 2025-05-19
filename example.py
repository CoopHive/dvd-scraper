#!/usr/bin/env python3
from openalex_scraper import OpenAlexScraper

def main():
    # Initialize scraper with config file
    scraper = OpenAlexScraper('config.yaml')
    
    # Run the scraping process
    scraper.run()

if __name__ == "__main__":
    main() 