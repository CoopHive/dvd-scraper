#!/usr/bin/env python3
import argparse
from openalex_scraper.csv_scraper import CSVOpenAlexScraper

def main():
    parser = argparse.ArgumentParser(
        description="Test CSV → OpenAlex PDF scraper")
    parser.add_argument(
        "--config", default="config.yaml",
        help="YAML config file (default: config.yaml)")
    parser.add_argument(
        "--csv", default="female_longevity_papers_rows.csv",
        help="Input CSV file (default: female_longevity_papers_rows.csv)")
    parser.add_argument(
        "--max", type=int, default=100,
        help="Max papers to process (default: 100)")
    parser.add_argument(
        "--start", type=int, default=0,
        help="Start from row number (0-based, default: 0)")
    args = parser.parse_args()

    scraper = CSVOpenAlexScraper(config_path=args.config, csv_path=args.csv)
    scraper.run(max_papers=args.max, start_from=args.start)

if __name__ == "__main__":
    main()
