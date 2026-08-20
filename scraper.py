import os
import json
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

def clean_and_parse_statute(url):
    """Fetches and parses an individual MCA statute page with smart subsection formatting."""
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

    # 3. Match Section ID, Title, and Raw Body
    match = re.search(r'(\d+-\d+-\d+)\.\s*([^.]+)\.\s*(.*)', clean_text)
    if not match:
        return None

    section_id = match.group(1).strip()
    title = match.group(2).strip()
    raw_content = match.group(3).strip()

    # 4. PRESERVE CROSS-REFERENCES
    # Temporarily hide parentheses in phrases like "subsection (4)(b)" or "subsections (3) and (4)"
    protected_content = re.sub(
        r'(subsections?|sections?|titles?|chapters?|parts?)\s+(\(\d+\)|\([a-z]+\))+',
        lambda m: m.group(0).replace('(', '___OPEN___').replace(')', '___CLOSE___'),
        raw_content,
        flags=re.IGNORECASE
    )
    # Also protect "subsection (4)(b)" style compound references
    protected_content = re.sub(
        r'(\(\d+\))(\([a-z]+\))',
        lambda m: m.group(1) + m.group(2).replace('(', '___OPEN___').replace(')', '___CLOSE___'),
        protected_content
    )

    # 5. SPLIT GENUINE SUBSECTIONS
    # Insert newlines before genuine subsection markers: (1), (a), (i), etc.
    formatted_content = re.sub(r'(\((?:\d+|[a-z]+|[A-Z]+)\))', r'\n\1', protected_content)

    # Restore hidden parentheses
    formatted_content = formatted_content.replace('___OPEN___', '(').replace('___CLOSE___', ')')

    # 6. CLEAN UP STANDALONE PARENT MARKERS
    # Merge orphaned parent markers like "(3)" directly with the following "(a)" line
    raw_lines = [line.strip() for line in formatted_content.split('\n') if line.strip()]
    cleaned_subsections = []
    
    i = 0
    while i < len(raw_lines):
        line = raw_lines[i]
        # Check if this line is just a bare marker like "(3)" or "(4)"
        if re.match(r'^\(\d+\)$', line) and (i + 1) < len(raw_lines):
            next_line = raw_lines[i + 1]
            # Merge with next line: "(3) (a) An offender..."
            cleaned_subsections.append(f"{line} {next_line}")
            i += 2  # Skip next line since we merged it
        else:
            cleaned_subsections.append(line)
            i += 1

    return {
        "id": section_id,
        "title": title,
        "source_url": url,
        "subsections": cleaned_subsections,
        "history": history,
        "bond_charges": []
    }

def get_links_from_page(url, keyword):
    """Helper function to find all links on a page matching a keyword."""
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
    # Get all Part index pages
    part_links = get_links_from_page(chapter_index_url, "sections_index.html")
    if not part_links:
        # Fallback in case chapter page links directly to parts_index or parts
        part_links = [chapter_index_url]

    print(f"   Found {len(part_links)} Parts.")

    # Get all individual Section URLs from every Part
    section_links = set()
    print("2. Discovering Sections in each Part...")
    for part_url in part_links:
        # Section links end with .html and are nested in section folders
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

    # Parse each section
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

    # Sort manifest numerically by statute ID (e.g., 45-5-101 before 45-5-201)
    index_manifest.sort(key=lambda x: [int(c) if c.isdigit() else c for c in x["id"].split("-")])

    # Save master index.json
    with open("data/index.json", "w", encoding="utf-8") as f:
        json.dump(index_manifest, f, indent=2)
        
    print(f"\nComplete! Saved {len(index_manifest)} statutes and generated data/index.json.")

if __name__ == "__main__":
    # Target: Title 45, Chapter 5
    chapter_url = "https://mca.legmt.gov/bills/mca/title_0450/chapter_0050/parts_index.html"
    scrape_mca_chapter(chapter_url)
