#!/usr/bin/env python3

import os
import csv
import requests
import yaml
import urllib.parse
import time
from typing import Optional, Dict, List
from pathlib import Path


class CSVOpenAlexScraper:
    def __init__(self, config_path: str, csv_path: str):
        """Initialize scraper with configuration from YAML file and CSV input."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.csv_path = csv_path
        self.session = self._make_session()

    def _make_session(self) -> requests.Session:
        """Create and configure requests session with headers."""
        s = requests.Session()
        s.headers.update({
            "User-Agent": self.config['user_agent'],
            "Referer": self.config['referer']
        })
        return s

    def read_csv_titles(self) -> List[Dict]:
        """Read CSV file and extract titles with metadata."""
        entries = []
        with open(self.csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = row.get('title', '').strip()
                if title and title != '[]':
                    entries.append({
                        'id': row.get('id'),
                        'pmid': row.get('pmid'),
                        'title': title,
                        'journal': row.get('journal'),
                        'publication_date': row.get('publication_date'),
                        'authors': row.get('authors')
                    })
        return entries

    def search_openalex_by_pmid(self, pmid: str) -> Optional[Dict]:
        """Retrieve the OpenAlex work for a given PMID via filter=ids.pmid."""
        if not pmid:
            return None

        params = {
            "filter": f"ids.pmid:{pmid}",
            "per-page": 1,
        }
        try:
            r = self.session.get(self.config['api_base'], params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            results = data.get("results", [])
            if not results:
                print(f"  → No OpenAlex record for PMID {pmid}")
                return None
            return results[0]
        except requests.HTTPError as e:
            print(f"  → HTTP {e.response.status_code} retrieving PMID {pmid}")
        except Exception as e:
            print(f"  → Error retrieving PMID {pmid}: {e}")
        return None

    def extract_pdf_from_work(self, work: Dict) -> Optional[Dict]:
        """Look through best_oa_location and all locations for the first pdf_url."""
        best = work.get("best_oa_location") or {}
        if best.get("pdf_url"):
            return {
                "pdf_url": best["pdf_url"],
                "doi": work.get("doi"),
                "openalex_id": work.get("id"),
                "title": work.get("title")
            }

        for loc in work.get("locations", []):
            if loc.get("pdf_url"):
                return {
                    "pdf_url": loc["pdf_url"],
                    "doi": work.get("doi"),
                    "openalex_id": work.get("id"),
                    "title": work.get("title")
                }

        return None

    def fetch_unpaywall(self, doi: str) -> Optional[str]:
        """Query Unpaywall for a public PDF URL via DOI, with proper URL‑encoding."""
        if not doi or not self.config.get('email'):
            return None

        # Clean up DOI - handle both formats: "https://doi.org/10.xxxx" and "10.xxxx"
        if doi.startswith("https://doi.org/"):
            doi_key = doi[16:]  # Remove "https://doi.org/" prefix
        elif doi.startswith("http://dx.doi.org/"):
            doi_key = doi[18:]  # Remove "http://dx.doi.org/" prefix  
        elif doi.startswith("doi:"):
            doi_key = doi[4:]   # Remove "doi:" prefix
        else:
            doi_key = doi       # Assume it's already clean

        # Don't URL-encode the DOI for Unpaywall - they expect it as-is
        endpoint = f"{self.config['unpaywall_api']}/{doi_key}"

        try:
            resp = requests.get(endpoint,
                                params={"email": self.config['email']},
                                timeout=20)
            if resp.status_code == 404:
                return None
            elif resp.status_code == 422:
                return None
                
            resp.raise_for_status()
            data = resp.json()
            loc = data.get("best_oa_location") or {}
            url = loc.get("url_for_pdf")
            if not url:
                print(f"  → No PDF found via Unpaywall for DOI {doi_key}")
            return url

        except requests.HTTPError as e:
            print(f"  → Unpaywall HTTP {e.response.status_code} for DOI {doi_key}")
        except Exception as e:
            print(f"  → Unpaywall lookup error for DOI {doi_key}: {e}")

        return None

    def download_pdf(self, url: str, original_title: str, paper_id: str, subdir: str) -> Optional[str]:
        """Download a PDF from a given URL into the specified subdir with improved headers."""
        os.makedirs(subdir, exist_ok=True)
        safe_title = "".join(c for c in original_title if c.isalnum() or c in (' ', '-', '_')).rstrip()[:50]
        filename = f"{paper_id}_{safe_title}.pdf"
        path = os.path.join(subdir, filename)

        if os.path.exists(path):
            print(f"    → Already exists: {filename}")
            return path

        # Enhanced headers to look more like a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/pdf,application/octet-stream,*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        try:
            # Use separate session with browser-like headers
            with requests.Session() as session:
                session.headers.update(headers)
                
                # First make a HEAD request to check if accessible
                head_resp = session.head(url, timeout=30, allow_redirects=True)
                if head_resp.status_code == 403:
                    print(f"    → Publisher blocking access (403) - trying direct download anyway")
                
                # Try the download
                r = session.get(url, stream=True, timeout=60, allow_redirects=True)
                
                # Check if we got HTML instead of PDF (common redirect trick)
                content_type = r.headers.get('content-type', '').lower()
                if 'text/html' in content_type:
                    print(f"    → Got HTML instead of PDF (likely paywall redirect)")
                    return None
                    
                r.raise_for_status()
                
                with open(path, "wb") as f:
                    for chunk in r.iter_content(8192):
                        f.write(chunk)
                
                # Verify it's actually a PDF by checking file size and first few bytes
                if os.path.getsize(path) < 1024:  # Less than 1KB probably not a real PDF
                    print(f"    → Downloaded file too small, likely error page")
                    os.remove(path)
                    return None
                    
                # Check PDF magic bytes
                with open(path, 'rb') as f:
                    header = f.read(4)
                    if not header.startswith(b'%PDF'):
                        print(f"    → Downloaded file is not a valid PDF")
                        os.remove(path)
                        return None
                
                return path
                
        except requests.HTTPError as e:
            if e.response.status_code == 403:
                print(f"    → Publisher blocking access (403 Forbidden)")
            elif e.response.status_code == 404:
                print(f"    → PDF not found (404)")
            else:
                print(f"    → HTTP error {e.response.status_code}")
        except Exception as e:
            print(f"    → Download error for {filename}: {e}")
            
        return None

    def process_single_paper(self, paper: Dict) -> Optional[str]:
        """Process a single paper: try OpenAlex then Unpaywall fallback."""
        title = paper['title']
        paper_id = paper.get('id') or paper['pmid']
        pmid = paper['pmid']

        print(f"  → Searching PMID {pmid}: {title}")
        work = self.search_openalex_by_pmid(pmid)
        if work:
            print("    → Found in OpenAlex")
            pdf = self.extract_pdf_from_work(work)
            if pdf and pdf.get("pdf_url"):
                path = self.download_pdf(pdf["pdf_url"], title, paper_id, self.config['outdir'])
                if path:
                    print(f"    → Downloaded via OpenAlex: {os.path.basename(path)}")
                    return path

            # fallback to Unpaywall if no PDF_url in OpenAlex
            doi = work.get("doi")
            fallback_url = self.fetch_unpaywall(doi)
            if fallback_url:
                path = self.download_pdf(fallback_url, title, paper_id, "pdf_2")
                if path:
                    print(f"    → Downloaded via Unpaywall: {os.path.basename(path)}")
                    return path
        else:
            print(f"    → No OpenAlex record; skipping Unpaywall")

        print("    → No PDF available")
        return None

    def run(self, max_papers: Optional[int] = None, start_from: int = 0):
        """Execute the CSV scraping process."""
        papers = self.read_csv_titles()
        if start_from > 0:
            papers = papers[start_from:]
        if max_papers:
            papers = papers[:max_papers]

        print(f"Processing {len(papers)} papers")
        found = downloaded = failed = 0

        for i, paper in enumerate(papers, 1):
            print(f"[{i}/{len(papers)}]")
            path = self.process_single_paper(paper)
            if path:
                downloaded += 1
            else:
                failed += 1
            found += 1

        print("\nSummary:")
        print(f"  Papers processed:        {found}")
        print(f"  Successfully downloaded: {downloaded}")
        print(f"  Failed to find/download:{failed}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CSV → OpenAlex PDF scraper")
    parser.add_argument("config", help="Path to YAML config")
    parser.add_argument("csv", help="Path to CSV input")
    parser.add_argument("--max", type=int, default=None, help="Max papers to process")
    parser.add_argument("--start", type=int, default=0, help="Start index (0-based)")
    args = parser.parse_args()

    scraper = CSVOpenAlexScraper(args.config, args.csv)
    scraper.run(max_papers=args.max, start_from=args.start)
