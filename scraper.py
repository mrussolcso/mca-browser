import os
import json
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

def clean_and_parse_statute(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    # 1. STRIP NAVIGATION & DISCLAIMERS FROM DOM
    # Remove top navs, headers, footers, and disclaimers before parsing text
    for junk in soup.find_all(['nav', 'header', 'footer', 'script', 'style']):
        junk.decompose()

    # 2. EXTRACT LEGISLATIVE HISTORY
    history = ""
    for p in soup.find_all('p'):
        p_text = p.get_text().strip()
        if p_text.startswith("History:"):
            history = p_text.replace("History:", "").strip()
            p.decompose()  # Remove from DOM so it doesn't leak into body content
        elif "Disclaimer:" in p_text:
            p.decompose()

    # 3. LOCATE CATCHLINE & SECTION ID
    # MCA pages use standard paragraph structures for statute body
    all_text = soup.get_text()
    match = re.search(r'(\d+-\d+-\d+)\.\s*([^.]+)\.\s*(.*)', all_text, re.DOTALL)
    if not match:
        return None

    section_id = match.group(1).strip()
    title = match.group(2).strip()
    raw_body = match.group(3).strip()

    # Strip any remaining top nav string artifacts before section ID
    clean_body = ' '.join(raw_body.split())

    # 4. STRUCTURAL BREAK LOOKAHEAD
    # Splits ONLY on true subsection starts: (1), (a), (i) at boundary positions
    pattern = r'(?=\b\((?:\d+|[a-z]+|[A-Z]+)\)\s+[A-Z"\(])'
    chunks = [c.strip() for c in re.split(pattern, clean_body) if c.strip()]

    # 5. MERGE BARE PARENT MARKERS
    # Fixes "(3) (a)" sitting on its own line above "(i)"
    subsections = []
    i = 0
    while i < len(chunks):
        curr = chunks[i]
        # If current line is just a marker like "(3) (a)" or "(3)", merge with next block
        if re.match(r'^\((?:\d+|[a-z]+)\)(\s*\((?:\d+|[a-z]+)\))?$', curr) and (i + 1) < len(chunks):
            subsections.append(f"{curr} {chunks[i+1]}")
            i += 2
        else:
            subsections.append(curr)
            i += 1

    return {
        "id": section_id,
        "title": title,
        "source_url": url,
        "subsections": subsections,
        "history": history,
        "bond_charges": []
    }

def get_links_from_page(url, keyword):
    """Finds links matching a keyword."""
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return []
    except Exception:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    links = set()
    for a in soup.find_all('a', href=True):
        href = a['href']
        if keyword in href:
            links.add(urljoin(url, href))
    return list(links)

def scrape_mca_chapter(chapter_index_url):
    """Crawls Chapter -> Parts -> Sections."""
    print("1. Discovering Parts in Chapter...")
    part_links = get_links_from_page(chapter_index_url, "sections_index.html")
    if not part_links:
        part_links = [chapter_index_url]

    print(f"   Found {len(part_links)} Parts.")

    section_links = set()
    print("2. Discovering Sections in each Part...")
    for part_url in part_links:
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(part_url, headers=headers)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.endswith('.html') and 'index' not in href:
                    section_links.add(urljoin(part_url, href))

    print(f"   Found {len(section_links)} total section pages.")

    os.makedirs("data", exist_ok=True)
    index_manifest = []

    for url in sorted(section_links):
        data = clean_and_parse_statute(url)
        if data:
            output_file = f"data/{data['id']}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            
            index_manifest.append({
                "id": data["id"],
                "title": data["title"],
                "file": f"{data['id']}.json"
            })
            print(f"Successfully processed: MCA {data['id']} - {data['title']}")

    index_manifest.sort(key=lambda x: [int(c) if c.isdigit() else c for c in x["id"].split("-")])

    with open("data/index.json", "w", encoding="utf-8") as f:
        json.dump(index_manifest, f, indent=2)
        
    print(f"\nComplete! Saved {len(index_manifest)} statutes and generated data/index.json.")

if __name__ == "__main__":
    chapter_url = "https://mca.legmt.gov/bills/mca/title_0450/chapter_0050/parts_index.html"
    scrape_mca_chapter(chapter_url)
