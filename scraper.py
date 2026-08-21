import os
import json
import re
import requests
from bs4 import BeautifulSoup

def transform_citation_links(soup):
    """
    Converts external MCA HTML links into internal web app anchors (#45-5-231).
    """
    for a in soup.find_all('a'):
        text = a.get_text().strip()
        # Check if link text matches a statute pattern like "45-5-206"
        statute_match = re.search(r'\b\d+-\d+-\d+\b', text)
        if statute_match:
            statute_id = statute_match.group(0)
            a.replace_with(f'<a class="statute-link" href="#{statute_id}">{text}</a>')
        else:
            a.replace_with(text)

def parse_statute_tree(law_id, raw_paragraphs):
    nodes = []
    
    # State tracking for parent hierarchy
    root_id = f"{law_id}(0)"
    active_paths = {0: root_id}

    # Index 0 check: Does text start before any subsection marker?
    first_p = raw_paragraphs[0] if raw_paragraphs else ""
    has_lead_in = not bool(re.search(r'^\(\d+\)', first_p))

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
        # Strip HTML tags temporarily to evaluate structural markers
        p_text = BeautifulSoup(p_html, "html.parser").get_text().strip()
        
        markers = re.findall(r'\((?:\d+|[a-z]+|[A-Z]+)\)', p_text)
        if not markers:
            continue

        l1_match = re.search(r'^\((\d+)\)', p_text)
        l2_match = re.search(r'\(([a-z])\)', p_text)
        l3_match = re.search(r'\((i|ii|iii|iv|v|vi|vii|viii|ix|x)\)', p_text)
        l4_match = re.search(r'\(([A-Z])\)', p_text)
        l5_match = re.search(r'\((I|II|III|IV|V|VI|VII|VIII|IX|X)\)', p_text)

        # 1. Stacked Parents Case: e.g. "(3) (a) (i)"
        if l1_match and l2_match and l3_match:
            p1, p2, p3 = l1_match.group(0), l2_match.group(0), l3_match.group(0)
            
            # (3)
            g1 = f"{law_id}{p1}"
            nodes.append({"global_id": g1, "path": p1, "parent": root_id, "indent": 1, "text": None})
            active_paths[1] = g1

            # (3)(a)
            g2 = f"{law_id}{p1}{p2}"
            nodes.append({"global_id": g2, "path": f"{p1}{p2}", "parent": g1, "indent": 2, "text": None})
            active_paths[2] = g2

            # (3)(a)(i)
            g3 = f"{law_id}{p1}{p2}{p3}"
            clean_html = re.sub(r'^(?:<[^>]+>|\s)*(\((?:\d+|[a-z]+|[A-Z]+)\)\s*)+', '', p_html).strip()
            nodes.append({"global_id": g3, "path": f"{p1}{p2}{p3}", "parent": g2, "indent": 3, "text": clean_html})
            active_paths[3] = g3

        # 2. Standard Level 1: (1)
        elif l1_match:
            p1 = l1_match.group(0)
            g1 = f"{law_id}{p1}"
            clean_html = re.sub(r'^(?:<[^>]+>|\s)*\(\d+\)\s*', '', p_html).strip()
            nodes.append({"global_id": g1, "path": p1, "parent": root_id, "indent": 1, "text": clean_html})
            active_paths[1] = g1

        # 3. Standard Level 2: (a)
        elif l2_match:
            p2 = l2_match.group(0)
            parent = active_paths.get(1, root_id)
            parent_path = parent.replace(law_id, "")
            g2 = f"{parent}{p2}"
            clean_html = re.sub(r'^(?:<[^>]+>|\s)*\([a-z]\)\s*', '', p_html).strip()
            nodes.append({"global_id": g2, "path": f"{parent_path}{p2}", "parent": parent, "indent": 2, "text": clean_html})
            active_paths[2] = g2

        # 4. Standard Level 3: (i)
        elif l3_match:
            p3 = l3_match.group(0)
            parent = active_paths.get(2, active_paths.get(1, root_id))
            parent_path = parent.replace(law_id, "")
            g3 = f"{parent}{p3}"
            clean_html = re.sub(r'^(?:<[^>]+>|\s)*\((?:i|ii|iii|iv|v|vi|vii|viii|ix|x)\)\s*', '', p_html).strip()
            nodes.append({"global_id": g3, "path": f"{parent_path}{p3}", "parent": parent, "indent": 3, "text": clean_html})
            active_paths[3] = g3

    return nodes

def scrape_statute(law_id, url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return

    soup = BeautifulSoup(response.text, 'html.parser')

    # Convert external statute hyperlinks to app relative routes
    transform_citation_links(soup)

    # Decompose non-content DOM elements
    for element in soup.find_all(['nav', 'header', 'footer', 'script', 'style', 'form', 'iframe']):
        element.decompose()

    # Extract history
    history = ""
    for p in soup.find_all('p'):
        text = p.get_text().strip()
        if text.startswith("History:"):
            history = text.replace("History:", "").strip()
            p.decompose()
        elif "Disclaimer:" in text or "Montana Code Annotated" in text:
            p.decompose()

    # Collect inner HTML strings for paragraph blocks
    raw_paragraphs = []
    clean_title = ""

    for p in soup.find_all('p'):
        p_text = p.get_text().strip()
        if not p_text:
            continue

        # Extract title line if present
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
        "source_url": url,
        "history": history,
        "nodes": nodes
    }

    os.makedirs("data", exist_ok=True)
    with open(f"data/{law_id}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    print(f"Exported data/{law_id}.json with {len(nodes)} relational nodes.")

if __name__ == "__main__":
    scrape_statute(
        "45-5-206", 
        "https://mca.legmt.gov/bills/mca/title_0450/chapter_0050/part_0020/section_0060/0450-0050-0020-0060.html"
    )
