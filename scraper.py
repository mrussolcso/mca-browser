import os
import json
import re
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

def clean_and_parse_statute(url):
    """Parses MCA pages by relying on the state site's native line breaks."""
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return None
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    # Get lines preserved by HTML structure
    text = soup.get_text()
    raw_lines = [line.strip() for line in text.splitlines() if line.strip()]

    # Filter out disclaimers and page clutter
    clean_lines = []
    history = ""
    for line in raw_lines:
        if line.lower().startswith("disclaimer:"):
            break
        if line.startswith("History:"):
            history = line.replace("History:", "").strip()
            break
        clean_lines.append(line)

    full_body = " ".join(clean_lines)

    # Match ID, Title, and Raw Body Text
    match = re.search(r'(\d+-\d+-\d+)\.\s*([^.]+)\.\s*(.*)', full_body)
    if not match:
        return None

    section_id = match.group(1).strip()
    title = match.group(2).strip()
    content = match.group(3).strip()

    # Split ONLY on structural markers at the start of new provisions:
    # Pattern looks for (1), (a), (i) preceded by space/start and followed by space + Capital/Letter/Quote
    pattern = r'(?=\s*\((?:\d+|[a-z]+|[A-Z]+)\)\s+[A-Z"\(])'
    raw_subsections = re.split(pattern, content)

    subsections = []
    for sub in raw_subsections:
        cleaned = sub.strip()
        if not cleaned:
            continue
        
        # If a line is just an empty marker like "(3) (a)", merge with previous or handle cleanly
        if subsections and re.match(r'^\((?:\d+|[a-z]+)\)\s*\((?:\d+|[a-z]+)\)$', subsections[-1]):
            subsections[-1] = f"{subsections[-1]} {cleaned}"
        else:
            subsections.append(cleaned)

    # Final cleanup pass for remaining stacked markers like "(3) (a)"
    final_subsections = []
    i = 0
    while i < len(subsections):
        curr = subsections[i]
        # Check for bare marker lines like "(3) (a)"
        if re.match(r'^\((?:\d+|[a-z]+|[A-Z]+)\)(?:\s*\((?:\d+|[a-z]+|[A-Z]+)\))?$', curr) and i + 1 < len(subsections):
            final_subsections.append(f"{curr} {subsections[i+1]}")
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
