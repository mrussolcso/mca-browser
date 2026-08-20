import os
import json
import re
import requests
from bs4 import BeautifulSoup

def clean_and_parse_45_5_206():
    """Fetches MCA 45-5-206, strips DOM clutter, and outputs clean structured JSON."""
    url = "https://mca.legmt.gov/bills/mca/title_0450/chapter_0050/part_0020/section_0060/0450-0050-0020-0060.html"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    print(f"Fetching statute from: {url}")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Failed to fetch page. Status code: {response.status_code}")
            return
    except Exception as e:
        print(f"Error fetching URL: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')

    # 1. REMOVE ALL DOM NOISE & UI NAVIGATION
    for element in soup.find_all(['nav', 'header', 'footer', 'script', 'style', 'form', 'iframe']):
        element.decompose()

    # 2. EXTRACT LEGISLATIVE HISTORY
    history = ""
    for p in soup.find_all('p'):
        text = p.get_text().strip()
        if text.startswith("History:"):
            history = text.replace("History:", "").strip()
            p.decompose()
        elif "Disclaimer:" in text or "Montana Code Annotated" in text:
            p.decompose()

    # Get remaining paragraph blocks from cleaned DOM
    paragraphs = [p.get_text().strip() for p in soup.find_all('p') if p.get_text().strip()]
    if not paragraphs:
        print("Error: No paragraph content found on page.")
        return

    full_text = " ".join(" ".join(paragraphs).split())

    # Filter out disclaimers or trailing metadata
    full_text = re.sub(r'Disclaimer:.*$', '', full_text, flags=re.IGNORECASE).strip()

    # 3. EXTRACT SECTION ID, TITLE, AND BODY CONTENT
    match = re.search(r'(\d+-\d+-\d+)\.\s*([^.]+)\.\s*(.*)', full_text)
    if not match:
        print("Error: Could not match statute structure (ID / Title / Body).")
        return

    section_id = match.group(1).strip()
    
    # Strip any header breadcrumb leak from the catchline title
    raw_title = match.group(2).strip()
    clean_title = raw_title.split("Montana Code Annotated")[0].split("MCA")[0].strip()
    
    raw_content = match.group(3).strip()

    # 4. TOKENIZE BODY BY STRUCTURAL SUBSECTION MARKERS
    pattern = r'(\((?:\d+|[a-z]+|[A-Z]+)\))'
    tokens = re.split(pattern, raw_content)

    raw_subsections = []
    current_buffer = ""

    for token in tokens:
        token_str = token.strip()
        if not token_str:
            continue
        
        # Check if current token is a marker (e.g., "(1)", "(a)", "(i)")
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

    # 5. MERGE BARE / STACKED PARENT MARKERS
    final_subsections = []
    i = 0
    while i < len(raw_subsections):
        curr = raw_subsections[i]
        
        # If current item is just a marker with no body text (e.g. "(3) (a)" or "(3)")
        if re.match(r'^\((?:\d+|[a-z]+)\)(\s*\((?:\d+|[a-z]+)\))?$', curr) and (i + 1) < len(raw_subsections):
            merged = f"{curr} {raw_subsections[i+1]}"
            final_subsections.append(merged)
            i += 2
        else:
            final_subsections.append(curr)
            i += 1

    # 6. ASSEMBLE JSON STRUCTURE
    data = {
        "id": section_id,
        "title": clean_title,
        "source_url": url,
        "subsections": final_subsections,
        "history": history,
        "bond_charges": []
    }

    # Save to data directory
    os.makedirs("data", exist_ok=True)
    output_path = f"data/{section_id}.json"
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    # Generate a single-entry index manifest
    index_manifest = [{
        "id": section_id,
        "title": clean_title,
        "file": f"{section_id}.json"
    }]
    
    with open("data/index.json", "w", encoding="utf-8") as f:
        json.dump(index_manifest, f, indent=2)

    print(f"\nSuccess! Saved {output_path} and data/index.json")

if __name__ == "__main__":
    clean_and_parse_45_5_206()
