import os
import json
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

def clean_and_parse_statute(url):
    """Fetches and parses an MCA statute page cleanly by paragraph structure."""
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    # Extract all text paragraphs or body blocks
    paragraphs = soup.find_all('p')
    if paragraphs:
        text_blocks = [p.get_text().strip() for p in paragraphs if p.get_text().strip()]
    else:
        # Fallback if no <p> tags exist
        body_text = soup.body.get_text() if soup.body else soup.get_text()
        text_blocks = [line.strip() for line in body_text.split('\n') if line.strip()]

    full_text = " ".join(" ".join(text_blocks).split())

    # 1. Strip disclaimers
    full_text = re.sub(r'Disclaimer:.*$', '', full_text, flags=re.IGNORECASE).strip()

    # 2. Extract History
    history = ""
    history_match = re.search(r'History:\s*(.*)', full_text)
    if history_match:
        history = history_match.group(1).strip()
        full_text = re.sub(r'History:\s*.*', '', full_text).strip()

    # 3. Match Section ID, Catchline, and Content
    match = re.search(r'(\d+-\d+-\d+)\.\s*([^.]+)\.\s*(.*)', full_text)
    if not match:
        return None

    section_id = match.group(1).strip()
    title = match.group(2).strip()
    raw_content = match.group(3).strip()

    # 4. Smart Line Splitting: Split only on markers at structural boundaries
    # Looks for markers like (1), (a), (i) preceded by space/start and followed by text
    tokens = re.split(r'(\((?:\d+|[a-z]+|[A-Z]+)\))', raw_content)

    subsections = []
    current_line = ""

    for token in tokens:
        token_str = token.strip()
        if not token_str:
            continue
        
        # Check if the token is a subsection marker like (1), (a), (i)
        if re.match(r'^\((?:\d+|[a-z]+|[A-Z]+)\)$', token_str):
            if current_line:
                subsections.append(current_line.strip())
            current_line = token_str
        else:
            if current_line:
                current_line += " " + token_str
            else:
                current_line = token_str

    if current_line:
        subsections.append(current_line.strip())

    # 5. Merge Orphaned Structural Headers (e.g., merge "(3)" and "(a)" onto one line)
    merged_subsections = []
    i = 0
    while i < len(subsections):
        line = subsections[i]
        # If line is just a bare number marker like "(3)" or "(4)"
        if re.match(r'^\(\d+\)$', line) and (i + 1) < len(subsections):
            next_line = subsections[i + 1]
            merged_subsections.append(f"{line} {next_line}")
            i += 2
        else:
            merged_subsections.append(line)
            i += 1

    return {
        "id": section_id,
        "title": title,
        "source_url": url,
        "subsections": merged_subsections,
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
