import os
import json
import re
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

def build_mca_url(law_id):
    """
    Constructs and verifies the MCA URL for a statute ID (e.g., '45-5-102').
    Format: title_0450/chapter_0050/part_0010/section_0020/0450-0050-0010-0020.html
    """
    match = re.match(r'^(\d+)-(\d+)-(\d+)$', law_id.strip())
    if not match:
        raise ValueError(f"Invalid Statute ID format: '{law_id}'. Expected format like '45-5-102'.")

    title_num, chapter_num, section_raw = [int(x) for x in match.groups()]
    
    # In MCA URLs, section 102 maps to section number 20 (section_0020 / -0020)
    section_num = section_raw % 100

    title_str = f"{title_num * 10:04d}"
    chapter_str = f"{chapter_num * 10:04d}"
    section_str = f"{section_num * 10:04d}"

    headers = {'User-Agent': 'Mozilla/5.0'}

    # Test candidate part numbers (part 1 to 15) to resolve the exact URL path
    for part_num in range(1, 16):
        part_str = f"{part_num * 10:04d}"
        candidate_url = (
            f"https://mca.legmt.gov/bills/mca/title_{title_str}/"
            f"chapter_{chapter_str}/part_{part_str}/section_{section_str}/"
            f"{title_str}-{chapter_str}-{part_str}-{section_str}.html"
        )
        
        response = requests.get(candidate_url, headers=headers, timeout=5)
        if response.status_code == 200:
            return candidate_url

    raise Exception(f"Could not locate a valid MCA webpage for statute ID {law_id}.")

def fetch_clean_statute_html(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch {url}: HTTP {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')
    
    for element in soup.find_all(['nav', 'header', 'footer', 'script', 'style', 'form', 'iframe']):
        element.decompose()

    return str(soup.body) if soup.body else str(soup)

def parse_statute_with_ai(law_id, title_short, url):
    raw_html = fetch_clean_statute_html(url)

    prompt = f"""
    You are a legal data engineer. Parse the provided HTML for Montana Code Annotated (MCA) section {law_id}.
    Return a strictly formatted JSON object matching this schema:

    {{
      "law_id": "{law_id}",
      "title_full": "Exact full title string (e.g. Deliberate homicide)",
      "title_short": "{title_short}",
      "source_url": "{url}",
      "history": "Legislative history string starting with En. Sec... (or empty string if not present)",
      "nodes": [
        {{
          "global_id": "{law_id}(0)",
          "path": "(0)",
          "parent": null,
          "indent": 0,
          "text": "Any introductory preamble text appearing BEFORE section (1). If no lead-in text exists, set this to null."
        }},
        {{
          "global_id": "{law_id}(1)",
          "path": "(1)",
          "parent": "{law_id}(0)",
          "indent": 1,
          "text": "Content of subsection (1) stripped of leading '(1)' marker."
        }}
      ]
    }}

    Rules:
    1. Every node must have an accurate global_id (e.g., "{law_id}(3)(a)(i)"), path, parent, indent level, and text.
    2. Convert any inline statute citations (like "45-5-231") into relative HTML links: <a class="statute-link" href="#45-5-231">45-5-231</a>.
    3. If a container node like (3) or (3)(a) has no direct body text of its own, set its "text" field to null.
    4. Strip leading marker prefixes like "(1)", "(a)", or "(i)" from the "text" field content.

    Raw HTML Input:
    {raw_html}
    """

    client = genai.Client()
    chat = client.chats.create(
        model="gemini-3.6-flash",
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    
    response = chat.send_message(prompt)
    statute_json = json.loads(response.text)

    os.makedirs("data", exist_ok=True)
    out_path = f"data/{law_id}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(statute_json, f, indent=4)

    print(f"Successfully processed and saved {out_path}")

if __name__ == "__main__":
    statute_id = os.environ.get("STATUTE_ID", "").strip()
    title_short = os.environ.get("TITLE_SHORT", "").strip()

    if not statute_id or not title_short:
        print("Error: STATUTE_ID and TITLE_SHORT environment variables are required.")
        exit(1)

    print(f"Target Statute ID: {statute_id}")
    print(f"Short Title: {title_short}")

    try:
        url = build_mca_url(statute_id)
        print(f"Resolved MCA URL: {url}")
        parse_statute_with_ai(statute_id, title_short, url)
    except Exception as err:
        print(f"Fatal error processing statute: {err}")
        exit(1)
