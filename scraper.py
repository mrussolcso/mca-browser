import os
import json
import requests
from bs4 import BeautifulSoup

def clean_and_parse_45_5_206():
    url = "https://mca.legmt.gov/bills/mca/title_0450/chapter_0050/part_0020/section_0060/0450-0050-0020-0060.html"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"Failed to fetch page: {response.status_code}")
            return
    except Exception as e:
        print(f"Error fetching URL: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')

    # 1. PRESERVE CITATION LINK TEXT
    # Converts <a> tags like <a href="...">45-5-231</a> into plain "45-5-231" text
    for a in soup.find_all('a'):
        a.replace_with(a.get_text())

    # 2. REMOVE DOM NOISE
    for element in soup.find_all(['nav', 'header', 'footer', 'script', 'style', 'form', 'iframe']):
        element.decompose()

    # 3. EXTRACT LEGISLATIVE HISTORY & DISCLAIMERS
    history = ""
    for p in soup.find_all('p'):
        text = p.get_text().strip()
        if text.startswith("History:"):
            history = text.replace("History:", "").strip()
            p.decompose()
        elif "Disclaimer:" in text or "Montana Code Annotated" in text:
            p.decompose()

    # 4. ITERATE THROUGH HTML PARAGRAPHS DIRECTLY
    subsections = []
    section_id = "45-5-206"
    clean_title = "Partner or family member assault -- penalty"

    for p in soup.find_all('p'):
        text = " ".join(p.get_text().split()).strip()
        if not text:
            continue
        
        # Strip out title header line if encountered in body paragraphs
        if text.startswith(f"{section_id}."):
            # Remove "45-5-206. Partner or family member assault -- penalty." from start
            text = text.replace(f"{section_id}. {clean_title}.", "").strip()
            if not text:
                continue

        subsections.append(text)

    # 5. SAVE JSON OUTPUT
    data = {
        "id": section_id,
        "title": clean_title,
        "source_url": url,
        "subsections": subsections,
        "history": history,
        "bond_charges": []
    }

    os.makedirs("data", exist_ok=True)
    with open(f"data/{section_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    index_manifest = [{"id": section_id, "title": clean_title, "file": f"{section_id}.json"}]
    with open("data/index.json", "w", encoding="utf-8") as f:
        json.dump(index_manifest, f, indent=2)

    print(f"Successfully processed {section_id} into data/{section_id}.json")

if __name__ == "__main__":
    clean_and_parse_45_5_206()
