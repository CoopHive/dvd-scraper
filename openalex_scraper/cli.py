#!/usr/bin/env python3
import argparse
import os
from .scraper import OpenAlexScraper

def main():
    parser = argparse.ArgumentParser(
        description="Download open access PDFs from OpenAlex"
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.config):
        print(f"Error: Configuration file not found: {args.config}")
        return 1

    try:
        scraper = OpenAlexScraper(args.config)
        scraper.run()
        return 0
    except Exception as e:
        print(f"Error: {str(e)}")
        return 1

if __name__ == "__main__":
    exit(main()) 