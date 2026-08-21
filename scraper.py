import os
import json
import re
import requests
from bs4 import BeautifulSoup

def transform_citation_links(soup):
    """Converts external MCA statute hyperlinks into internal relative anchors."""
    for a in soup.find_all('a'):
        text = a.get_text().strip()
        statute_match = re.search(r'\b\d+-\d+-\d+\b', text)
        if statute_match:
            statute_id = statute_match.group(0)
            a.replace_with(f'<a class="statute-link" href="#{statute_id}">{text}</a>')
        else:
            a.replace_with(text)

def classify_marker(token):
    """Identifies statutory hierarchy level for a marker token."""
    if re.match(r'^\(\d+\)$', token):
        return 1  # (1), (2), (3)
    if re.match(r'^\([a-z]\)$', token):
        return 2  # (a), (b), (c)
    if re.match(r'^\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\)$', token):
        return 3  # (i), (ii), (iii)
    if re.match(r'^\([A-Z]\)$', token):
        return 4  # (A), (B), (C)
    if re.match(r'^\((?:I|II|III|IV|V|VI|VII|VIII|IX|X)\)$', token):
        return 5  # (I), (II), (III)
    return None

def parse_statute_tree(law_id, raw_paragraphs):
    root_id = f"{law_id}(0)"
    nodes = []

    # Stack holds tuples of (level_number, marker_string, global_id)
    stack = [(0, "(0)", root_id)]

    # Check if the first paragraph starts without a level 1 marker like (1)
    first_p = raw_paragraphs[0] if raw_paragraphs else ""
    first_p_text = BeautifulSoup(first_p, "html.parser").get_text().strip()
    has_lead_in = not bool(re.search(r'^\(\d+\)', first_p_text))

    if has_lead_in and raw_paragraphs:
        lead_in_text = raw_paragraphs.pop(0)
        nodes.append({
            "global_id": root_id,
            "path": "(0)",
            "parent": None,
            "indent": 0,
            "text": lead_in_text
        })
    else:
        nodes.append({
            "global_id": root_id,
            "path": "(0)",
            "parent": None,
            "indent": 0,
            "text": None
        })

    for p_html in raw_paragraphs:
        p_text = BeautifulSoup(p_html, "html.parser").get_text().strip()
        
        match = re.match(r'^((?:\s*\((?:\d+|[a-z]+|[A-Z]+)\))+)\s*(.*)', p_text)
        if not match:
            continue

        raw_markers_str = match.group(1).strip()
        markers = re.findall(r'\((?:\d+|[a-z]+|[A-Z]+)\)', raw_markers_str)

        if not markers:
            continue

        for idx, marker in enumerate(markers):
            m_level = classify_marker(marker)
            if not m_level:
                continue

            while stack and stack[-1][0] >= m_level:
                stack.pop()

            parent_info = stack[-1] if stack else (0, "(0)", root_id)
            parent_global_id = parent_info[2]
            parent_path = parent_info[2].replace(law_id, "")

            if parent_path == "(0)":
                current_path = marker
            else:
                current_path = f"{parent_path}{marker}"

            current_global_id = f"{law_id}{current_path}"
            is_last_marker = (idx == len(markers) - 1)

            if is_last_marker:
                clean_html = re.sub(r'^(?:<[^>]+>|\s)*(\((?:\d+|[a-z]+|[A-Z]+)\)\s*)+', '', p_html).strip()
                node_text = clean_html
            else:
                node_text = None

            nodes.append({
                "global_id": current_global_id,
                "path": current_path,
                "parent": parent_global_id,
                "indent": m_level,
                "text": node_text
            })

            stack.append((m_level, marker, current_global_id))

    return nodes

def scrape_statute(law_id, url, title_short):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            print(f"[{law_id}] Fetch failed: Status {response.status_code}")
            return None
    except Exception as e:
        print(f"[{law_id}] Fetch error: {e}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')

    transform_citation_links(soup)

    for element in soup.find_all(['nav', 'header', 'footer', 'script', 'style', 'form', 'iframe']):
        element.decompose()

    history = ""
    for p in soup.find_all('p'):
        text = p.get_text().strip()
        if text.startswith("History:"):
            history = text.replace("History:", "").strip()
            p.decompose()
        elif "Disclaimer:" in text or "Montana Code Annotated" in text:
            p.decompose()

    raw_paragraphs = []
    clean_title = ""

    for p in soup.find_all('p'):
        p_text = p.get_text().strip()
        if not p_text:
            continue

        if p_text.startswith(f"{law_id}."):
            title_match = re.search(rf'{re.escape(law_id)}\.\s*([^.]+)\.', p_text)
            if title_match:
                clean_title = title_match.group(1).strip()
            continue

        raw_paragraphs.append("".join(str(c) for c in p.contents).strip())

    nodes = parse_statute_tree(law_id, raw_paragraphs)

    data = {
        "law_id": law_id,
        "title_full": clean_title,
        "title_short": title_short,
        "source_url": url,
        "history": history,
        "nodes": nodes
    }

    os.makedirs("data", exist_ok=True)
    with open(f"data/{law_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    # Output Level-0 status directly to terminal
    print(f"\n--- {law_id} ({clean_title}) ---")
    print(f"Level 0 Node: {json.dumps(nodes[0], indent=2)}")
    print(f"Total Nodes: {len(nodes)}")

    return {"id": law_id, "title": clean_title, "file": f"{law_id}.json"}

if __name__ == "__main__":
    statutes_to_scrape = [
        {
            "id": "45-5-206",
            "short": "PFMA",
            "url": "https://mca.legmt.gov/bills/mca/title_0450/chapter_0050/part_0020/section_0060/0450-0050-0020-0060.html"
        },
        {
            "id": "45-5-231",
            "short": "Offender Intervention",
            "url": "https://mca.legmt.gov/bills/mca/title_0450/chapter_0050/part_0020/section_0310/0450-0050-0020-0310.html"
        }
    ]

    index_manifest = []
    for stat in statutes_to_scrape:
        entry = scrape_statute(stat["id"], stat["url"], stat["short"])
        if entry:
            index_manifest.append(entry)

    with open("data/index.json", "w", encoding="utf-8") as f:
        json.dump(index_manifest, f, indent=4)
