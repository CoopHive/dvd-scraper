# OpenAlex PDF Scraper

A Python tool for downloading open access PDFs from OpenAlex with Unpaywall fallback support.

## Requirements

- Python 3.8 or higher
- pyenv (recommended for Python version management)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/openalex-scraper.git
cd openalex-scraper
```

2. Set up Python environment with pyenv:
```bash
# Install Python version if not already installed
pyenv install 3.11.7

# pyenv will automatically use the correct version due to .python-version file
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install the package in development mode:
```bash
pip install -e .
```

## Configuration

Edit the `config.yaml` file to customize your scraping parameters:

```yaml
# Search parameters
topic: "machine learning"  # Required: Search term
per_page: 20              # Results per page (max 200)
pages: 1                  # How many pages to fetch
min_citations: null       # Minimum number of citations

# Download settings
outdir: "pdfs"           # Directory to save PDFs
workers: 4               # Parallel download threads
email: null              # Your email for Unpaywall API
```

## Usage

### As a Command Line Tool

```bash
openalex-scraper
```

### As a Python Module

```python
from openalex_scraper import OpenAlexScraper

scraper = OpenAlexScraper('config.yaml')
scraper.run()
```

## License

MIT License 