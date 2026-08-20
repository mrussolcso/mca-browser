import os
import json
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

def clean_and_parse_statute(url):
    """Fetches and parses an individual MCA statute page into structured JSON."""
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    # 1. PURGE UI NAVIGATION & DOM NOISE
    # Strips out navigation bars, headers, footers, and scripts before reading text
    for element in soup.find_all(['nav', 'header', 'footer', 'script', 'style', 'form']):
        element.decompose()

    # 2. EXTRACT LEGISLATIVE HISTORY & DISCLAIMERS
    history = ""
    for p in soup.find_all('p'):
        p_text = p.get_text().strip()
        if p_text.startswith("History:"):
            history = p_text.replace("History:", "").strip()
            p.decompose()
        elif "Disclaimer:" in p_text or "Montana Code Annotated" in p_text:
            p.decompose()

    # Get remaining raw lines from cleaned DOM
    raw_lines = [line.strip() for line in soup.get_text().splitlines() if line.strip()]

    # Filter out residual header breadcrumbs
    clean_lines = []
    for line in raw_lines:
        if any(keyword in line for keyword in ["Toggle navigation", "MCA Contents", "Search Help", "Part Contents"]):
            continue
        clean_lines.append(line)

    full_body = " ".join(clean_lines)

    # 3. MATCH SECTION ID, TITLE, AND BODY
    match = re.search(r'(\d+-\d+-\d+)\.\s*([^.]+)\.\s*(.*)', full_body)
    if not match:
        return None

    section_id = match.group(1).strip()
    title = match.group(2).strip()
    raw_content = match.group(3).strip()

    # 4. TOKENIZE BY STRUCTURAL MARKERS
    # Split text into tokens based on markers like (1), (a), (i)
    pattern = r'(\((?:\d+|[a-z]+|[A-Z]+)\))'
    tokens = re.split(pattern, raw_content)

    raw_subsections = []
    current_buffer = ""

    for token in tokens:
        token_str = token.strip()
        if not token_str:
            continue
        
        # Check if token is a structural marker
        if re.match(r'^\((?:\d+|[a-z]+|[A-Z]+)\)$', token_str):
            if current_buffer:
                raw_subsections.append(current_buffer.strip())
            current_buffer = token_str
        else:
            if current_buffer:
                current_buffer += " " + token_str
            else:
                current_buffer = token_str

    if current_buffer:
        raw_subsections.append(current_buffer.strip())

    # 5. MERGE STACKED PARENT MARKERS
    # Combines bare markers like "(3) (a)" directly with their text payload "(i) An offender..."
    final_subsections = []
    i = 0
    while i < len(raw_subsections):
        curr = raw_subsections[i]
        
        # If line is just a marker without sentence body
        if re.match(r'^\((?:\d+|[a-z]+)\)(\s*\((?:\d+|[a-z]+)\))?$', curr) and (i + 1) < len(raw_subsections):
            merged = f"{curr} {raw_subsections[i+1]}"
            final_subsections.append(merged)
            i += 2
        else:
            final_subsections.append(curr)
            i += 1

    return {
        "id": section_id,
        "title": title,
        "source_url": url,
        "subsections": final_subsections,
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
