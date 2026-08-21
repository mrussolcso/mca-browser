import os
import json
import datetime
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

def parse_statute_with_ai(law_id, title_short, url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch {url}: HTTP {response.status_code}")

    soup = BeautifulSoup(response.text, 'html.parser')
    for element in soup.find_all(['nav', 'header', 'footer', 'script', 'style', 'form', 'iframe']):
        element.decompose()

    raw_html = str(soup.body) if soup.body else str(soup)

    prompt = f"""
    You are a legal data engineer. Parse the provided HTML for Montana Code Annotated (MCA) section {law_id}.
    Return a strictly formatted JSON object matching this schema:

    {{
      "law_id": "{law_id}",
      "title_full": "Exact full title string (e.g. Partner or family member assault -- penalty)",
      "title_short": "{title_short}",
      "source_url": "{url}",
      "last_scraped": "{datetime.datetime.utcnow().isoformat()}Z",
      "history": "Exact text of the history string starting with 'En. Sec...' (or empty string if not present)",
      "nodes": [
        {{
          "global_id": "{law_id}(0)",
          "path": "(0)",
          "parent": null,
          "indent": 0,
          "text": "Any introductory preamble text appearing BEFORE section (1). If no lead-in text exists, set this to null."
        }}
      ]
    }}

    Rules:
    1. Every node must have an accurate global_id, path, parent, indent level, and text.
    2. Convert any inline statute citations (like "45-5-231") into relative HTML links: <a class="statute-link" href="#45-5-231">45-5-231</a>.
    3. If a container node has no direct body text of its own, set its "text" field to null.
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
    with open(f"data/{law_id}.json", "w", encoding="utf-8") as f:
        json.dump(statute_json, f, indent=4)

    print(f"Successfully scraped and saved data/{law_id}.json")

if __name__ == "__main__":
    statute_id = os.environ.get("STATUTE_ID", "45-5-206").strip()
    title_short = os.environ.get("TITLE_SHORT", "PFMA").strip()
    
    # Read URL from index.json if available
    url = f"https://mca.legmt.gov/bills/mca/title_0450/chapter_0050/part_0020/section_0060/0450-0050-0020-0060.html"
    if os.path.exists("data/index.json"):
        with open("data/index.json", "r", encoding="utf-8") as f:
            manifest = json.load(f)
            for item in manifest:
                if item["law_id"] == statute_id:
                    url = item["url"]
                    break

    parse_statute_with_ai(statute_id, title_short, url)
