import os
import json
import re
import requests
from bs4 import BeautifulSoup

def clean_and_parse_statute(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch page: {response.status_code}")
        return None

    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Extract body text
    body_text = soup.body.get_text() if soup.body else soup.get_text()
    clean_text = ' '.join(body_text.split())

    # 1. Remove Disclaimer completely
    clean_text = re.sub(r'Disclaimer:.*$', '', clean_text, flags=re.IGNORECASE).strip()

    # 2. Extract History section if present
    history = ""
    history_match = re.search(r'History:\s*(.*)', clean_text)
    if history_match:
        history = history_match.group(1).strip()
        clean_text = re.sub(r'History:\s*.*', '', clean_text).strip()

    # 3. Extract Section ID and Title
    match = re.search(r'(\d+-\d+-\d+)\.\s*([^.]+)\.\s*(.*)', clean_text)
    if not match:
        print("Could not match standard MCA formatting structure.")
        return None

    section_id = match.group(1).strip()
    title = match.group(2).strip()
    raw_content = match.group(3).strip()

    # 4. Split content into readable lines/subsections
    # Places breaks before (1), (2), (a), (b), (i), (ii), etc.
    formatted_content = re.sub(r'(\((?:\d+|[a-z]+|[A-Z]+)\))', r'\n\1', raw_content).strip()
    subsections = [line.strip() for line in formatted_content.split('\n') if line.strip()]

    return {
        "id": section_id,
        "title": title,
        "source_url": url,
        "subsections": subsections,
        "history": history,
        "bond_charges": []  # Ready for future Bond Book integration
    }

if __name__ == "__main__":
    test_url = "https://mca.legmt.gov/bills/mca/title_0450/chapter_0050/part_0020/section_0010/0450-0050-0020-0010.html"
    
    print("Scraping MCA 45-5-201...")
    data = clean_and_parse_statute(test_url)
    
    if data:
        os.makedirs("data", exist_ok=True)
        output_file = f"data/{data['id']}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        print(f"Success! Saved formatted statute to {output_file}")
