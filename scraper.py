import os
import json
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

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

    # Automatically retrieves key from GEMINI_API_KEY environment variable
    client = genai.Client()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )

    statute_json = json.loads(response.text)

    os.makedirs("data", exist_ok=True)
    with open(f"data/{law_id}.json", "w", encoding="utf-8") as f:
        json.dump(statute_json, f, indent=4)

    print(f"Successfully processed {law_id}.json")

if __name__ == "__main__":
    parse_statute_with_ai(
        law_id="45-5-206", 
        title_short="PFMA", 
        url="https://mca.legmt.gov/bills/mca/title_0450/chapter_0050/part_0020/section_0060/0450-0050-0020-0060.html"
    )
    parse_statute_with_ai(
        law_id="45-5-231", 
        title_short="Offender Intervention", 
        url="https://mca.legmt.gov/bills/mca/title_0450/chapter_0050/part_0020/section_0310/0450-0050-0020-0310.html"
    )
