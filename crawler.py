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
MAX_WORKERS = 15  # Number of concurrent requests


def compute_hash(text: str) -> str:
    normalized = " ".join(text.strip().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def fetch_soup(url: str, retries=3):
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            if response.status_code == 200:
                return BeautifulSoup(response.text, "html.parser")
        except Exception:
            if attempt < retries - 1:
                time.sleep(1 * (attempt + 1))
                continue
    return None


def scrape_section(s_url, p_url):
    s_soup = fetch_soup(s_url)
    if not s_soup:
        return None

    s_link_elem = s_soup.find("a", href=True)
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
    logging.info("Starting High-Speed MCA Sitemap Crawl...")
    sitemap = []
    
    soup = fetch_soup(BASE_URL)
    if not soup:
        logging.error("Could not reach MCA homepage.")
        return

    title_links = soup.find_all("a", href=re.compile(r"title_"))
    section_tasks = []

    for t_link in title_links:
        t_url = urljoin(BASE_URL, t_link.get("href"))
        t_soup = fetch_soup(t_url)
        if not t_soup:
            continue

        chap_links = t_soup.find_all("a", href=re.compile(r"chapter_"))
        for c_link in chap_links:
            c_url = urljoin(t_url, c_link.get("href"))
            c_soup = fetch_soup(c_url)
            if not c_soup:
                continue

            part_links = c_soup.find_all("a", href=re.compile(r"part_"))
            for p_link in part_links:
                p_url = urljoin(c_url, p_link.get("href"))
                p_soup = fetch_soup(p_url)
                if not p_soup:
                    continue

                sec_links = p_soup.find_all("a", href=re.compile(r"\d+-\d+-\d+\.html|\.html"))
                for s_link in sec_links:
                    s_url = urljoin(p_url, s_link.get("href"))
                    section_tasks.append((s_url, p_url))

    logging.info(f"Discovered {len(section_tasks)} sections. Fetching concurrently...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(scrape_section, s_url, p_url): s_url for s_url, p_url in section_tasks}
        
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                sitemap.append(res)

    output_filename = f"mca_sitemap_{time.strftime('%Y%m%d')}.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(sitemap, f, indent=2)

    with open("mca_sitemap_latest.json", "w", encoding="utf-8") as f:
        json.dump(sitemap, f, indent=2)

    logging.info(f"Crawl complete! Total sections mapped: {len(sitemap)}. Saved.")


if __name__ == "__main__":
    run_crawler()
