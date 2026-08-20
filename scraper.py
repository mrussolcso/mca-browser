import os
import json
import re
import requests
from bs4 import BeautifulSoup

def build_subsection_tree(raw_paragraphs):
    subsections = [
        {
            "path": "(0)",
            "parent": None,
            "indent": 0,
            "text": None
        }
    ]

    # Map to keep track of active paths at each indentation level
    active_paths = {0: "(0)"}

    for p_text in raw_paragraphs:
        # Find all structural markers like (1), (a), (i) in the paragraph
        markers = re.findall(r'\((?:\d+|[a-z]+|[A-Z]+)\)', p_text)
        if not markers:
            continue

        # Extract specific level types from markers
        l1_match = re.search(r'^\((\d+)\)', p_text)
        l2_match = re.search(r'\(([a-z])\)', p_text)
        l3_match = re.search(r'\((i|ii|iii|iv|v|vi|vii|viii|ix|x)\)', p_text)

        # Case 1: Stacked Parent Container like "(3) (a)"
        if l1_match and l2_match and not l3_match and len(markers) == 2:
            l1_tag = l1_match.group(0)
            l2_tag = l2_match.group(0)

            # Insert Level 1 parent null container
            p1_path = l1_tag
            subsections.append({
                "path": p1_path,
                "parent": "(0)",
                "indent": 1,
                "text": None
            })
            active_paths[1] = p1_path

            # Insert Level 2 parent null container
            p2_path = f"{p1_path}{l2_tag}"
            subsections.append({
                "path": p2_path,
                "parent": p1_path,
                "indent": 2,
                "text": None
            })
            active_paths[2] = p2_path

        # Case 2: Deeply Stacked Container like "(3) (a) (i)"
        elif l1_match and l2_match and l3_match:
            l1_tag = l1_match.group(0)
            l2_tag = l2_match.group(0)
            l3_tag = l3_match.group(0)

            p1_path = l1_tag
            subsections.append({
                "path": p1_path,
                "parent": "(0)",
                "indent": 1,
                "text": None
            })
            active_paths[1] = p1_path

            p2_path = f"{p1_path}{l2_tag}"
            subsections.append({
                "path": p2_path,
                "parent": p1_path,
                "indent": 2,
                "text": None
            })
            active_paths[2] = p2_path

            p3_path = f"{p2_path}{l3_tag}"
            clean_body = re.sub(r'^(\((?:\d+|[a-z]+|[A-Z]+)\)\s*)+', '', p_text).strip()
            subsections.append({
                "path": p3_path,
                "parent": p2_path,
                "indent": 3,
                "text": clean_body
            })
            active_paths[3] = p3_path

        # Case 3: Standard Level 1 item like "(1)" or "(2)"
        elif l1_match:
            l1_tag = l1_match.group(0)
            p1_path = l1_tag
            clean_body = re.sub(r'^\(\d+\)\s*', '', p_text).strip()
            subsections.append({
                "path": p1_path,
                "parent": "(0)",
                "indent": 1,
                "text": clean_body
            })
            active_paths[1] = p1_path

        # Case 4: Standard Level 2 item like "(a)" or "(b)"
        elif l2_match:
            l2_tag = l2_match.group(0)
            parent = active_paths.get(1, "(0)")
            p2_path = f"{parent}{l2_tag}"
            clean_body = re.sub(r'^\([a-z]\)\s*', '', p_text).strip()
            subsections.append({
                "path": p2_path,
                "parent": parent,
                "indent": 2,
                "text": clean_body
            })
            active_paths[2] = p2_path

        # Case 5: Standard Level 3 item like "(i)" or "(ii)"
        elif l3_match:
            l3_tag = l3_match.group(0)
            parent = active_paths.get(2, active_paths.get(1, "(0)"))
            p3_path = f"{parent}{l3_tag}"
            clean_body = re.sub(r'^\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\)\s*', '', p_text).strip()
            subsections.append({
                "path": p3_path,
                "parent": parent,
                "indent": 3,
                "text": clean_body
            })
            active_paths[3] = p3_path

    return subsections

def clean_and_parse_45_5_206():
    url = "https://mca.legmt.gov/bills/mca/title_0450/chapter_0050/part_0020/section_0060/0450-0050-0020-0060.html"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return
    except Exception as e:
        print(f"Fetch failed: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')

    # Convert citation links to plain text inside paragraph
    for a in soup.find_all('a'):
        a.replace_with(a.get_text())

    # Decompose navigation and headers
    for element in soup.find_all(['nav', 'header', 'footer', 'script', 'style', 'form', 'iframe']):
        element.decompose()

    # Extract Legislative History
    history = ""
    for p in soup.find_all('p'):
        text = p.get_text().strip()
        if text.startswith("History:"):
            history = text.replace("History:", "").strip()
            p.decompose()
        elif "Disclaimer:" in text or "Montana Code Annotated" in text:
            p.decompose()

    # Get body paragraphs
    raw_paragraphs = []
    section_id = "45-5-206"
    clean_title = "Partner or family member assault -- penalty"

    for p in soup.find_all('p'):
        text = " ".join(p.get_text().split()).strip()
        if not text:
            continue
        if text.startswith(f"{section_id}."):
            text = text.replace(f"{section_id}. {clean_title}.", "").strip()
            if not text:
                continue
        raw_paragraphs.append(text)

    # Build the full hierarchical structure
    structured_subsections = build_subsection_tree(raw_paragraphs)

    data = {
        "law_id": section_id,
        "title_full": clean_title,
        "title_short": "PFMA",
        "source_url": url,
        "history": history,
        "subsections": structured_subsections
    }

    os.makedirs("data", exist_ok=True)
    with open(f"data/{section_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    index_manifest = [{"id": section_id, "title": clean_title, "file": f"{section_id}.json"}]
    with open("data/index.json", "w", encoding="utf-8") as f:
        json.dump(index_manifest, f, indent=4)

    print(f"Successfully exported data/{section_id}.json with hierarchical paths!")

if __name__ == "__main__":
    clean_and_parse_45_5_206()
