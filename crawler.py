import hashlib
import json
import logging
import os
import re
import time
import zipfile
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Official state bulk download URL (adjust year if necessary)
BULK_ZIP_URL = "https://mca.legmt.gov/bills/mca/mca_html.zip"  
ZIP_DEST = "mca_html.zip"
EXTRACT_DIR = "mca_extracted"


def compute_hash(text: str) -> str:
    normalized = " ".join(text.strip().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def download_and_extract():
    logging.info("Downloading bulk MCA zip file...")
    response = requests.get(BULK_ZIP_URL, stream=True, timeout=60)
    if response.status_code == 200:
        with open(ZIP_DEST, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logging.info("Download complete. Extracting files...")
        
        with zipfile.ZipFile(ZIP_DEST, 'r') as zip_ref:
            zip_ref.extractall(EXTRACT_DIR)
        logging.info("Extraction complete.")
        return True
    else:
        logging.error(f"Failed to download bulk archive. Status: {response.status_code}")
        return False


def parse_local_statutes():
    sitemap = []
    logging.info("Parsing local HTML files...")
    
    # Walk through extracted files on disk
    for root, _, files in os.walk(EXTRACT_DIR):
        for file in files:
            if file.endswith(".html") and not ("index" in file or "title" in file):
                filepath = os.path.join(root, file)
                
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    soup = BeautifulSoup(f.read(), "html.parser")

                # Extract section citation and title from HTML contents
                heading = soup.find(["h1", "h2", "h3", "p"])
                sec_name = heading.text.strip() if heading else file
                
                # Citation extraction (e.g., 1-1-101 from filename or content)
                citation = file.replace(".html", "")

                # Extract history string
                history_text = "No history recorded"
                history_elem = soup.find(string=re.compile(r"History:", re.IGNORECASE))
                if history_elem and history_elem.parent:
                    history_text = history_elem.parent.text.replace("History:", "").strip()

                sitemap.append({
                    "citation": citation,
                    "file_path": filepath,
                    "section_name": sec_name,
                    "raw_history": history_text,
                    "history_hash": compute_hash(history_text),
                    "last_indexed": time.strftime("%Y-%m-%d")
                })

    output_filename = "mca_sitemap_latest.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(sitemap, f, indent=2)

    logging.info(f"Fast indexing complete! Total sections indexed: {len(sitemap)}")


if __name__ == "__main__":
    if download_and_extract():
        parse_local_statutes()
