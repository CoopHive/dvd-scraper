import os
import requests
from concurrent.futures import ThreadPoolExecutor
import yaml
from typing import Optional, Dict, List


class OpenAlexScraper:
    def __init__(self, config_path: str):
        """Initialize scraper with configuration from YAML file."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.session = self._make_session()

    def _make_session(self) -> requests.Session:
        """Create and configure requests session with headers."""
        s = requests.Session()
        s.headers.update({
            "User-Agent": self.config['user_agent'],
            "Referer": self.config['referer']
        })
        return s

    def fetch_works(self, page: int) -> dict:
        """Query OpenAlex /works with filters and return JSON."""
        filters = ["is_oa:true"]
        if self.config['min_citations'] is not None:
            citation_threshold = self.config['min_citations'] - 1
            filters.append(f"cited_by_count:>{citation_threshold}")
        filter_str = ",".join(filters)

        params = {
            "filter": filter_str,
            "search": self.config['topic'],
            "per-page": self.config['per_page'],
            "page": page,
        }
        r = self.session.get(self.config['api_base'], params=params, timeout=30)
        r.raise_for_status()
        return r.json()

    def extract_entries(self, works_json: dict) -> List[dict]:
        """Extract PDF URLs and metadata from works JSON."""
        entries = []
        for w in works_json.get("results", []):
            oa = w.get("best_oa_location") or {}
            pdf = oa.get("pdf_url")
            if not pdf:
                continue
            entries.append({
                "pdf_url": pdf,
                "host_type": oa.get("host_type"),
                "doi": w.get("doi")
            })
        return entries

    def fetch_unpaywall(self, doi: str) -> Optional[str]:
        """Query Unpaywall for a public PDF URL via DOI."""
        if not doi or not self.config['email']:
            return None
        url = f"{self.config['unpaywall_api']}/{doi}"
        r = requests.get(url, params={"email": self.config['email']}, timeout=20)
        if r.status_code != 200:
            return None
        data = r.json()
        loc = data.get("best_oa_location") or {}
        return loc.get("url_for_pdf")

    def download_pdf(self, entry: Dict) -> str:
        """Download PDF from entry URL with Unpaywall fallback."""
        os.makedirs(self.config['outdir'], exist_ok=True)
        name = entry["pdf_url"].split("/")[-1].split("?")[0]
        path = os.path.join(self.config['outdir'], name)
        if os.path.exists(path):
            return path

        try:
            r = self.session.get(entry["pdf_url"], stream=True, timeout=60)
            r.raise_for_status()
        except requests.HTTPError as e:
            if e.response.status_code in (403, 429):
                fallback = self.fetch_unpaywall(entry.get("doi"))
                if fallback:
                    print(f"→ Publisher blocked. Retrying via Unpaywall: {fallback}")
                    r = self.session.get(fallback, stream=True, timeout=60)
                    r.raise_for_status()
                else:
                    raise
            else:
                raise

        with open(path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        return path

    def run(self):
        """Execute the scraping process."""
        entries = []

        for pg in range(1, self.config['pages'] + 1):
            js = self.fetch_works(pg)
            es = self.extract_entries(js)
            print(f"[Page {pg}] Found {len(es)} PDF entries")
            entries.extend(es)

        print(f"Total PDF entries: {len(entries)}")

        with ThreadPoolExecutor(max_workers=self.config['workers']) as ex:
            futures = [
                ex.submit(self.download_pdf, e)
                for e in entries
            ]
            for f in futures:
                try:
                    path = f.result()
                    print(f"Downloaded → {path}")
                except Exception as err:
                    print(f"Failed → {err}") 