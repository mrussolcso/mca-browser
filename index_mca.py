import os
import json
import re
import requests
from bs4 import BeautifulSoup

MCA_BASE_URL = "https://mca.legmt.gov/bills/mca"

def fetch_soup(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            print(f"Failed to fetch {url} (HTTP {res.status_code})")
            return None
        return BeautifulSoup(res.text, 'html.parser')
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def generate_full_index():
    print("Building full MCA structural index...")
    index_tree = []
    
    # 1. Fetch Root Index (mca/index.html)
    soup = fetch_soup(f"{MCA_BASE_URL}/index.html")
    if not soup:
        print("Fatal: Could not load main MCA root index page.")
        return

    # Look for links pointing to titles (e.g., href="title_0450/chapters_index.html")
    title_links = soup.find_all('a', href=re.compile(r'title_\d+'))
    print(f"Found {len(title_links)} titles in root index.")
    
    for t_link in title_links:
        t_text = t_link.get_text().strip()
        t_href = t_link['href']
        
        t_match = re.search(r'TITLE\s+(\d+)', t_text, re.IGNORECASE)
        if not t_match:
            continue
            
        title_num = t_match.group(1)
        print(f"Indexing Title {title_num}...")

        title_obj = {
            "title_num": title_num,
            "title_raw": t_text,
            "chapters": []
        }

        # Build absolute URL to the Title's chapters page
        title_url = f"{MCA_BASE_URL}/{t_href}" if not t_href.startswith('http') else t_href
        c_soup = fetch_soup(title_url)
        if not c_soup:
            continue

        chapter_links = c_soup.find_all('a', href=re.compile(r'chapter_\d+'))
        
        for c_link in chapter_links:
            c_text = c_link.get_text().strip()
            c_href = c_link['href']
            
            c_match = re.search(r'CHAPTER\s+(\d+)', c_text, re.IGNORECASE)
            if not c_match:
                continue

            chap_num = c_match.group(1)

            chapter_obj = {
                "chapter_num": chap_num,
                "chapter_raw": c_text,
                "statutes": []
            }

            # Build absolute URL to Chapter index
            base_dir = title_url.rsplit('/', 1)[0]
            chap_url = f"{base_dir}/{c_href}" if not c_href.startswith('http') else c_href
            s_soup = fetch_soup(chap_url)
            
            if s_soup:
                for s_link in s_soup.find_all('a', href=True):
                    s_text = s_link.get_text().strip()
                    law_match = re.search(r'\b\d+-\d+-\d+\b', s_text)
                    
                    if law_match:
                        law_id = law_match.group(0)
                        s_href = s_link['href']
                        
                        s_base_dir = chap_url.rsplit('/', 1)[0]
                        full_statute_url = f"{s_base_dir}/{s_href}" if not s_href.startswith('http') else s_href

                        if not any(st["law_id"] == law_id for st in chapter_obj["statutes"]):
                            chapter_obj["statutes"].append({
                                "law_id": law_id,
                                "url": full_statute_url
                            })

            title_obj["chapters"].append(chapter_obj)

        index_tree.append(title_obj)

    os.makedirs("data", exist_ok=True)
    with open("data/mca_index.json", "w", encoding="utf-8") as f:
        json.dump(index_tree, f, indent=2)

    print("MCA Indexing complete! Written to data/mca_index.json")

if __name__ == "__main__":
    generate_full_index()
