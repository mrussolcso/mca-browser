import os
import json
import re
import requests
from bs4 import BeautifulSoup

def scrape_mca_section(url):
    """
    Downloads an MCA statute page, cleans the content, 
    and returns a structured dictionary.
    """
    # Fetch the webpage
    headers = {'User-Agent': 'Mozilla/5.0'}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch page: {response.status_code}")
        return None

    # Parse HTML with BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # MCA pages keep text inside the <body> tag
    body_text = soup.body.get_text() if soup.body else soup.get_text()
    
    # Clean up whitespace
    clean_text = ' '.join(body_text.split())

    # Extract Section Number, Title, and Content using Regex
    # Matches patterns like: "45-5-201. Assault."
    match = re.search(r'(\d+-\d+-\d+)\.\s*([^.]+)\.\s*(.*)', clean_text)
    
    if match:
        section_id = match.group(1).strip()     # e.g., "45-5-201"
        title = match.group(2).strip()          # e.g., "Assault"
        content = match.group(3).strip()        # Rest of the statute text
        
        return {
            "id": section_id,
            "title": title,
            "content": content,
            "source_url": url
        }
    else:
        print("Could not match MCA formatting pattern.")
        return None

if __name__ == "__main__":
    # Test URL: MCA 45-5-201 (Assault)
    test_url = "https://mca.legmt.gov/bills/mca/title_0450/chapter_0050/part_0020/section_0010/0450-0050-0020-0010.html"
    
    print("Scraping MCA 45-5-201...")
    data = scrape_mca_section(test_url)
    
    if data:
        # Create 'data' folder if it doesn't exist
        os.makedirs("data", exist_ok=True)
        
        # Save output to data/45-5-201.json
        output_file = f"data/{data['id']}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            
        print(f"Success! Saved statute to {output_file}")
