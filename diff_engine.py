import json
import os
import sys

def load_sitemap(filepath):
    if not os.path.exists(filepath):
        print(f"Error: File {filepath} not found.")
        sys.exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {item["citation"]: item for item in data}

def generate_diff(old_file, new_file):
    old_data = load_sitemap(old_file)
    new_data = load_sitemap(new_file)

    revised_sections = []
    new_sections = []
    removed_sections = []

    for citation, new_item in new_data.items():
        if citation not in old_data:
            new_sections.append(new_item)
        elif new_item["history_hash"] != old_data[citation]["history_hash"]:
            revised_sections.append({
                "citation": citation,
                "url": new_item["url"],
                "old_history": old_data[citation]["raw_history"],
                "new_history": new_item["raw_history"],
                "needs_text_rescrape": True
            })

    for citation, old_item in old_data.items():
        if citation not in new_data:
            removed_sections.append(old_item)

    diff_report = {
        "summary": {
            "total_new": len(new_sections),
            "total_revised": len(revised_sections),
            "total_removed": len(removed_sections),
        },
        "revised_sections": revised_sections,
        "new_sections": new_sections,
        "removed_sections": removed_sections
    }

    report_file = "diff_rescrape_queue.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(diff_report, f, indent=2)

    print("=== Scan Comparison Complete ===")
    print(f"New Statutes: {len(new_sections)}")
    print(f"Revised Statutes: {len(revised_sections)}")
    print(f"Removed Statutes: {len(removed_sections)}")
    print(f"Flagged items queued for full text scrape saved to: {report_file}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python diff_engine.py <older_sitemap.json> <newer_sitemap.json>")
    else:
        generate_diff(sys.argv[1], sys.argv[2])
