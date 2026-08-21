import os
import json
import re
import requests
from bs4 import BeautifulSoup

MCA_BASE_URL = "https://mca.legmt.gov/bills/mca"

def fetch_soup(url):
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers, timeout=10)
    if res.status_code != 200:
        return None
    return BeautifulSoup(res.text, 'html.parser')

def generate_full_index():
    print("Building full MCA structural index...")
    index_tree = []
    
    # 1. Fetch Titles Index
    soup = fetch_soup(f"{MCA_BASE_URL}/title_index.html")
    if not soup:
        print("Failed to load root Title index.")
        return

    title_links = soup.find_all('a', href=re.compile(r'title_\d+'))
    
    for t_link in title_links:
        t_text = t_link.get_text().strip()
        t_href = t_link['href']
        
        # Match Title Number and Name
        t_match = re.search(r'TITLE\s+(\d+)\.\s*(.*)', t_text, re.IGNORECASE)
        if not t_match:
            continue
            
        title_num = t_match.group(1)
        title_name = t_match.group(2)
        print(f"Indexing Title {title_num}: {title_name}")

        title_obj = {
            "title_num": title_num,
            "title_name": title_name,
            "chapters": []
        }

        # 2. Fetch Chapters for this Title
        title_url = f"{MCA_BASE_URL}/{t_href}"
        c_soup = fetch_soup(title_url)
        if not c_soup:
            continue

        chapter_links = c_soup.find_all('a', href=re.compile(r'chapter_\d+'))
        
        for c_link in chapter_links:
            c_text = c_link.get_text().strip()
            c_href = c_link['href']
            
            c_match = re.search(r'CHAPTER\s+(\d+)\.\s*(.*)', c_text, re.IGNORECASE)
            if not c_match:
                continue

            chap_num = c_match.group(1)
            chap_name = c_match.group(2)

            chapter_obj = {
                "chapter_num": chap_num,
                "chapter_name": chap_name,
                "statutes": []
            }

            # 3. Fetch Statutes in Chapter
            chap_url = title_url.rsplit('/', 1)[0] + '/' + c_href
            s_soup = fetch_soup(chap_url)
            if not s_soup:
                continue

            for s_link in s_soup.find_all('a', href=True):
                s_text = s_link.get_text().strip()
                law_match = re.search(r'\b\d+-\d+-\d+\b', s_text)
                
                if law_match:
                    law_id = law_match.group(0)
                    s_href = s_link['href']
                    full_statute_url = chap_url.rsplit('/', 1)[0] + '/' + s_href

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

    print(f"MCA Indexing complete! Written to data/mca_index.json")

if __name__ == "__main__":
    generate_full_index()
