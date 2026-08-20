import os
import json
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

def clean_and_parse_statute(url):
    """Fetches and parses an MCA statute page cleanly into structured JSON."""
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    # 1. PURGE UI & NAVIGATION DOM ELEMENTS
    for element in soup.find_all(['nav', 'header', 'footer', 'script', 'style', 'form', 'a']):
        element.decompose()

    # 2. EXTRACT LEGISLATIVE HISTORY
    history = ""
    for p in soup.find_all('p'):
        text = p.get_text().strip()
        if text.startswith("History:"):
            history = text.replace("History:", "").strip()
            p.decompose()

    # 3. EXTRACT BODY PARAGRAPHS
    paragraphs = [p.get_text().strip() for p in soup.find_all('p') if p.get_text().strip()]
    if not paragraphs:
        return None

    full_text = " ".join(" ".join(paragraphs).split())

    # Filter disclaimers
    full_text = re.sub(r'Disclaimer:.*$', '', full_text, flags=re.IGNORECASE).strip()

    # 4. MATCH SECTION ID & CATCHLINE TITLE
    match = re.search(r'(\d+-\d+-\d+)\.\s*([^.]+)\.\s*(.*)', full_text)
    if not match:
        return None

    section_id = match.group(1).strip()
    # Truncate title at common header artifacts if present
    clean_title = match.group(2).split("Montana Code Annotated")[0].split("MCA")[0].strip()
    raw_content = match.group(3).strip()

    # 5. TOKENIZE BY STRUCTURAL SUBSECTION MARKERS
    pattern = r'(\((?:\d+|[a-z]+|[A-Z]+)\))'
    tokens = re.split(pattern, raw_content)

    subsections = []
    current_buffer = ""

    for token in tokens:
        token_str = token.strip()
        if not token_str:
            continue
        
        if re.match(r'^\((?:\d+|[a-z]+|[A-Z]+)\)$', token_str):
            if current_buffer:
                subsections.append(current_buffer.strip())
            current_buffer = token_str
        else:
            if current_buffer:
                current_buffer += " " + token_str
            else:
                current_buffer = token_str

    if current_buffer:
        subsections.append(current_buffer.strip())

    # 6. MERGE BARE PARENT MARKERS (e.g., "(3) (a)")
    final_subsections = []
    i = 0
    while i < len(subsections):
        curr = subsections[i]
        if re.match(r'^\((?:\d+|[a-z]+)\)(\s*\((?:\d+|[a-z]+)\))?$', curr) and (i + 1) < len(subsections):
            final_subsections.append(f"{curr} {subsections[i+1]}")
            i += 2
        else:
            final_subsections.append(curr)
            i += 1

    return {
        "id": section_id,
        "title": clean_title,
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
