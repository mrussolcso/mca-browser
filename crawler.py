import concurrent.futures
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
MAX_WORKERS = 20  # Number of concurrent connections


def compute_hash(text: str) -> str:
    normalized = " ".join(text.strip().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def fetch_soup(url: str, retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            if response.status_code == 200:
                return BeautifulSoup(response.text, "html.parser")
        except Exception:
            if attempt < retries - 1:
                time.sleep(0.5 * (attempt + 1))
                continue
    return None


def get_sublinks(url: str, pattern: str):
    """Helper to fetch a index page and extract matching links."""
    soup = fetch_soup(url)
    if not soup:
        return []
    links = soup.find_all("a", href=re.compile(pattern))
    return [urljoin(url, l.get("href")) for l in links if l.get("href")]


def scrape_section(s_url):
    s_soup = fetch_soup(s_url)
    if not s_soup:
        return None

    citation = s_url.split("/")[-1].replace(".html", "")
    heading_tag = s_soup.find(["h1", "h2", "h3", "p"])
    sec_name = heading_tag.text.strip() if heading_tag else "Unknown Section"

    history_text = "No history recorded"
    history_elem = s_soup.find(string=re.compile(r"History:", re.IGNORECASE))
    if history_elem and history_elem.parent:
        history_text = history_elem.parent.text.replace("History:", "").strip()

    return {
        "citation": citation,
        "url": s_url,
        "section_name": sec_name,
        "raw_history": history_text,
        "history_hash": compute_hash(history_text),
        "last_indexed": time.strftime("%Y-%m-%d")
    }


def run_crawler():
    start_time = time.time()
    logging.info("Starting Fully Concurrent MCA Sitemap Crawl...")

    # Phase 1: Get Title URLs
    soup = fetch_soup(BASE_URL)
    if not soup:
        logging.error("Could not reach MCA homepage.")
        return
    title_urls = [urljoin(BASE_URL, l.get("href")) for l in soup.find_all("a", href=re.compile(r"title_"))]
    logging.info(f"Found {len(title_urls)} titles. Finding chapters...")

    # Phase 2: Get Chapter URLs in Parallel
    chapter_urls = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(get_sublinks, t_url, r"chapter_") for t_url in title_urls]
        for f in concurrent.futures.as_completed(futures):
            chapter_urls.extend(f.result())
    logging.info(f"Found {len(chapter_urls)} chapters. Finding parts...")

    # Phase 3: Get Part URLs in Parallel
    part_urls = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(get_sublinks, c_url, r"part_") for c_url in chapter_urls]
        for f in concurrent.futures.as_completed(futures):
            part_urls.extend(f.result())
    logging.info(f"Found {len(part_urls)} parts. Finding sections...")

    # Phase 4: Get Section URLs in Parallel
    section_urls = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(get_sublinks, p_url, r"\d+-\d+-\d+\.html|\.html") for p_url in part_urls]
        for f in concurrent.futures.as_completed(futures):
            section_urls.extend(f.result())
    
    # Deduplicate section URLs
    section_urls = list(set(section_urls))
    logging.info(f"Discovered {len(section_urls)} total sections in {round(time.time() - start_time, 2)}s. Indexing section details...")

    # Phase 5: Fetch Section Metadata in Parallel
    sitemap = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(scrape_section, s_url): s_url for s_url in section_urls}
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res:
                sitemap.append(res)

    # Save output
    output_filename = f"mca_sitemap_{time.strftime('%Y%m%d')}.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(sitemap, f, indent=2)

    with open("mca_sitemap_latest.json", "w", encoding="utf-8") as f:
        json.dump(sitemap, f, indent=2)

    elapsed = round(time.time() - start_time, 2)
    logging.info(f"Crawl complete in {elapsed} seconds! Total sections mapped: {len(sitemap)}.")


if __name__ == "__main__":
    run_crawler()
