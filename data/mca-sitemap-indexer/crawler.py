import hashlib
import json
import logging
import re
import time
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

BASE_URL = "https://mca.legmt.gov/bills/mca/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MCA-Sitemap-Indexer/1.0"}


def compute_hash(text: str) -> str:
    """Normalize whitespace and calculate SHA-256 hash."""
    normalized = " ".join(text.strip().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def fetch_soup(url: str):
    """Fetch URL contents safely with basic retry logic."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        if response.status_code == 200:
            return BeautifulSoup(response.text, "html.parser")
        logging.warning(f"Failed to fetch {url} - Status Code: {response.status_code}")
    except Exception as e:
        logging.error(f"Error fetching {url}: {e}")
    return None


def run_crawler():
    logging.info("Starting MCA Sitemap Crawl...")
    sitemap = []
    
    soup = fetch_soup(BASE_URL)
    if not soup:
        logging.error("Could not reach MCA homepage. Exiting.")
        return

    # Find all title index links
    title_links = soup.find_all("a", href=re.compile(r"title_"))
    
    for t_link in title_links:
        t_href = t_link.get("href")
        t_url = urljoin(BASE_URL, t_href)
        t_title = t_link.text.strip()
        
        logging.info(f"Indexing Title: {t_title}")
        t_soup = fetch_soup(t_url)
        if not t_soup:
            continue

        # Find all chapter index links within title
        chap_links = t_soup.find_all("a", href=re.compile(r"chapter_"))
        
        for c_link in chap_links:
            c_url = urljoin(t_url, c_link.get("href"))
            c_soup = fetch_soup(c_url)
            if not c_soup:
                continue

            # Find all part index links within chapter
            part_links = c_soup.find_all("a", href=re.compile(r"part_"))
            
            for p_link in part_links:
                p_url = urljoin(c_url, p_link.get("href"))
                p_soup = fetch_soup(p_url)
                if not p_soup:
                    continue

                # Find all section links within part
                sec_links = p_soup.find_all("a", href=re.compile(r"\d+-\d+-\d+\.html|\.html"))
                
                for s_link in sec_links:
                    s_url = urljoin(p_url, s_link.get("href"))
                    s_soup = fetch_soup(s_url)
                    if not s_soup:
                        continue

                    # Extract section content details
                    citation = s_link.text.strip()
                    heading_tag = s_soup.find(["h1", "h2", "h3", "p"])
                    sec_name = heading_tag.text.strip() if heading_tag else "Unknown Section"

                    # Extract history string (usually located at bottom of page)
                    history_text = "No history recorded"
                    history_elem = s_soup.find(text=re.compile(r"History:", re.IGNORECASE))
                    if history_elem and history_elem.parent:
                        history_text = history_elem.parent.text.replace("History:", "").strip()

                    sitemap.append({
                        "citation": citation,
                        "url": s_url,
                        "section_name": sec_name,
                        "raw_history": history_text,
                        "history_hash": compute_hash(history_text),
                        "last_indexed": time.strftime("%Y-%m-%d")
                    })
                    time.sleep(0.05)  # Respectful throttle

    output_filename = f"mca_sitemap_{time.strftime('%Y%m%d')}.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(sitemap, f, indent=2)
    
    # Save a copy as 'mca_sitemap_latest.json' for easy tracking
    with open("mca_sitemap_latest.json", "w", encoding="utf-8") as f:
        json.dump(sitemap, f, indent=2)

    logging.info(f"Crawl complete. Total sections mapped: {len(sitemap)}. Saved to {output_filename}")


if __name__ == "__main__":
    run_crawler()
