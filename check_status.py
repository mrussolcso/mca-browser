import os
import json
import re
import requests
from bs4 import BeautifulSoup

def check_statute_needs_update(law_id, local_json_path, source_url):
    """Compares local legislative history against live page history."""
    try:
        with open(local_json_path, 'r', encoding='utf-8') as f:
            local_data = json.load(f)

        # Fetch live HTML history line
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(source_url, headers=headers, timeout=5)
        if res.status_code != 200:
            return False, "Live page unreachable"

        soup = BeautifulSoup(res.text, 'html.parser')
        live_history = ""
        for p in soup.find_all('p'):
            if p.get_text().strip().startswith("History:"):
                live_history = p.get_text().strip()
                break

        local_history = local_data.get("history", "")

        if live_history != local_history:
            return True, f"History changed! Live: '{live_history}' vs Local: '{local_history}'"
        
        return False, "Up to date"

    except Exception as e:
        return False, f"Error checking update: {e}"

def generate_manifest():
    if not os.path.exists("data/mca_index.json"):
        print("Error: data/mca_index.json not found. Run index_mca.py first.")
        return

    with open("data/mca_index.json", "r", encoding="utf-8") as f:
        index_tree = json.load(f)

    manifest = []
    total_found = 0
    total_scraped = 0
    outdated_count = 0

    for title in index_tree:
        for chapter in title["chapters"]:
            for statute in chapter["statutes"]:
                law_id = statute["law_id"]
                url = statute["url"]
                total_found += 1
                
                local_file = f"data/{law_id}.json"
                is_scraped = os.path.exists(local_file)
                needs_update = False
                reason = "Not scraped yet"

                if is_scraped:
                    total_scraped += 1
                    needs_update, reason = check_statute_needs_update(law_id, local_file, url)
                    if needs_update:
                        outdated_count += 1

                manifest.append({
                    "law_id": law_id,
                    "title": title["title_num"],
                    "chapter": chapter["chapter_num"],
                    "url": url,
                    "scraped": is_scraped,
                    "needs_update": needs_update,
                    "status_reason": reason
                })

    with open("data/index.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print("\n--- MCA Library Status Summary ---")
    print(f"Total Statutes Indexed: {total_found}")
    print(f"Total Statutes Scraped: {total_scraped}")
    print(f"Statutes Requiring Update: {outdated_count}")
    print(f"Progress: {(total_scraped / total_found * 100) if total_found else 0:.2f}% complete")
    print("Updated index written to data/index.json")

if __name__ == "__main__":
    generate_manifest()
