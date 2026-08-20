import os
import json
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

def clean_and_parse_statute(url):
    """Fetches and parses an individual MCA statute page."""
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    body_text = soup.body.get_text() if soup.body else soup.get_text()
    clean_text = ' '.join(body_text.split())

    # 1. Strip disclaimers
    clean_text = re.sub(r'Disclaimer:.*$', '', clean_text, flags=re.IGNORECASE).strip()

    # 2. Separate History
    history = ""
    history_match = re.search(r'History:\s*(.*)', clean_text)
    if history_match:
        history = history_match.group(1).strip()
        clean_text = re.sub(r'History:\s*.*', '', clean_text).strip()

    # 3. Match Section ID, Catchline, and Body
    match = re.search(r'(\d+-\d+-\d+)\.\s*([^.]+)\.\s*(.*)', clean_text)
    if not match:
        return None

    section_id = match.group(1).strip()
    title = match.group(2).strip()
    raw_content = match.group(3).strip()

    # 4. Format subsections into clean lists
    formatted_content = re.sub(r'(\((?:\d+|[a-z]+|[A-Z]+)\))', r'\n\1', raw_content).strip()
    subsections = [line.strip() for line in formatted_content.split('\n') if line.strip()]

    return {
        "id": section_id,
        "title": title,
        "source_url": url,
        "subsections": subsections,
        "history": history,
        "bond_charges": []
    }

def scrape_mca_chapter(chapter_index_url):
    """Crawls a Chapter index page to find and scrape all section pages."""
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(chapter_index_url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch chapter index: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find all links ending with .html that match section file patterns
    section_links = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.endswith('.html') and 'parts_index' not in href and 'chapters_index' not in href:
            full_url = urljoin(chapter_index_url, href)
            section_links.add(full_url)

    os.makedirs("data", exist_ok=True)
    index_manifest = []

    print(f"Found {len(section_links)} potential section pages in chapter.")

    for url in sorted(section_links):
        data = clean_and_parse_statute(url)
        if data:
            # Save individual statute JSON
            output_file = f"data/{data['id']}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            
            # Append entry to index manifest
            index_manifest.append({
                "id": data["id"],
                "title": data["title"],
                "file": f"{data['id']}.json"
            })
            print(f"Successfully processed: MCA {data['id']} - {data['title']}")

    # Sort index by section number
    index_manifest.sort(key=lambda x: [int(c) for c in x["id"].split("-")])

    # Save master index.json
    with open("data/index.json", "w", encoding="utf-8") as f:
        json.dump(index_manifest, f, indent=2)
        
    print(f"\nComplete! Processed {len(index_manifest)} statutes and generated data/index.json.")

if __name__ == "__main__":
    # Target: Title 45, Chapter 5 (Offenses Against the Person)
    chapter_url = "https://mca.legmt.gov/bills/mca/title_0450/chapter_0050/parts_index.html"
    scrape_mca_chapter(chapter_url)
