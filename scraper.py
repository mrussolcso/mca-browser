import os
import json
import time
import re
import requests
from bs4 import BeautifulSoup
from google import genai
from google.genai import types

def get_chapter_statutes(title_num, chapter_num):
    """Crawls chapter part indexes to discover all available statute URLs."""
    formatted_title = f"{int(title_num):04d}"
    formatted_chapter = f"{int(chapter_num):04d}"
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    statutes = []

    # Iterate through potential chapter parts (e.g., part 1 to part 20)
    for part in range(1, 21):
        formatted_part = f"{part:04d}"
        part_url = f"https://mca.legmt.gov/bills/mca/title_{formatted_title}/chapter_{formatted_chapter}/part_{formatted_part}/sections_index.html"
        
        response = requests.get(part_url, headers=headers, timeout=5)
        if response.status_code != 200:
            # Stop if we hit a part that doesn't exist
            if part > 1 and not statutes:
                continue
            elif part > 1:
                break

        soup = BeautifulSoup(response.text, 'html.parser')

        for a_tag in soup.find_all('a', href=True):
            text = a_tag.get_text().strip()
            statute_match = re.search(r'\b\d+-\d+-\d+\b', text)
            
            if statute_match:
                law_id = statute_match.group(0)
                href = a_tag['href']
                
                # Build absolute MCA URL
                if href.startswith('http'):
                    full_url = href
                else:
                    base_dir = part_url.rsplit('/', 1)[0]
                    full_url = f"{base_dir}/{href}"

                # Filter out reserved sections or duplicate entries
                if not any(s['id'] == law_id for s in statutes) and "reserved" not in text.lower():
                    statutes.append({
                        "id": law_id,
                        "short": law_id,
                        "url": full_url
                    })

    return statutes

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

    print(f"Successfully processed {law_id}.json")

if __name__ == "__main__":
    title_input = os.environ.get("TITLE_NUM", "45")
    chapter_input = os.environ.get("CHAPTER_NUM", "5")

    print(f"--- Crawling Title {title_input}, Chapter {chapter_input} ---")
    
    try:
        statutes_to_scrape = get_chapter_statutes(title_input, chapter_input)
        print(f"Found {len(statutes_to_scrape)} active statutes to process.")

        for idx, item in enumerate(statutes_to_scrape, 1):
            print(f"[{idx}/{len(statutes_to_scrape)}] Processing {item['id']}...")
            try:
                parse_statute_with_ai(item["id"], item["short"], item["url"])
            except Exception as e:
                print(f"Error processing {item['id']}: {e}")

            # 4-second delay keeps request rate under Gemini's 15 RPM limit
            time.sleep(4)

    except Exception as err:
        print(f"Fatal error: {err}")
