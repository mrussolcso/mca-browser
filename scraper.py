import os
import json
import re
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

def extract_law_id_from_url(url):
    """Extracts MCA section ID (e.g., '45-5-206') from an MCA URL or page content."""
    # Attempt extraction from common MCA URL pattern: .../0450-0050-0020-0060.html
    match = re.search(r'(\d{4})-(\d{4})-(\d{4})-(\d{4})\.html', url)
    if match:
        t, c, p, s = [int(x) for x in match.groups()]
        return f"{t}-{c}-{s}"
    
    # Fallback: search for standard statute ID pattern in the URL text
    match_alt = re.search(r'\b\d+-\d+-\d+\b', url)
    if match_alt:
        return match_alt.group(0)
        
    raise ValueError(f"Could not extract a valid law_id from URL: {url}")

def fetch_clean_statute_html(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch {url}: HTTP {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Try finding statute number in document text if URL parsing was ambiguous
    text_content = soup.get_text()
    
    for element in soup.find_all(['nav', 'header', 'footer', 'script', 'style', 'form', 'iframe']):
        element.decompose()

    return str(soup.body) if soup.body else str(soup), text_content

def parse_statute_with_ai(law_id, title_short, url):
    raw_html, text_content = fetch_clean_statute_html(url)

    # If law_id couldn't be strictly formatted from URL, infer from body text
    if not re.match(r'^\d+-\d+-\d+$', law_id):
        match = re.search(r'\b(\d+-\d+-\d+)\b', text_content)
        if match:
            law_id = match.group(1)

    prompt = f"""
    You are a legal data engineer. Parse the provided HTML for Montana Code Annotated (MCA) section {law_id}.
    Return a strictly formatted JSON object matching this schema:

    {{
      "law_id": "{law_id}",
      "title_full": "Exact full title string (e.g. Partner or family member assault -- penalty)",
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
    statute_url = os.environ.get("STATUTE_URL", "").strip()
    title_short = os.environ.get("TITLE_SHORT", "").strip()

    if not statute_url or not title_short:
        print("Error: STATUTE_URL and TITLE_SHORT environment variables are required.")
        exit(1)

    print(f"Processing URL: {statute_url}")
    print(f"Short Title: {title_short}")

    try:
        law_id = extract_law_id_from_url(statute_url)
        parse_statute_with_ai(law_id, title_short, statute_url)
    except Exception as err:
        print(f"Fatal error processing statute: {err}")
        exit(1)
