import json
import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


def extract_links(url):
    """Extract all links with page title and anchor text from the given webpage"""
    response = requests.get(url, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Get page title
    page_title = soup.title.string.strip() if soup.title else "No Title"

    links_data = []
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"])  # make full URL
        text = a.get_text(strip=True)   # clickable hypertext

        if href and text:  # only meaningful links
            links_data.append({
                "page_title": page_title,
                "hyper_text": text,
                "link": href
            })

    print(f"✅ Found {len(links_data)} links on {url}")
    return links_data


def sanitize_filename(name: str) -> str:
    """Make a safe lowercase filename allowing spaces, underscores, and hyphens."""
    print(name)
    safe = "".join(c for c in name if c.isalnum() or c in (" ", "_", "-"))
    return safe.lower().strip()

def extract_links_from_header_json(header_json_path="header_links.json", base_folder=None):
    """Extract links for each header and save them inside the same folder as header_links.json"""

    # ✅ Ensure the input file exists
    if not os.path.exists(header_json_path):
        raise FileNotFoundError(f"❌ {header_json_path} not found. Please run the header extraction first.")

    # ✅ Determine base folder from the input file's directory
    if base_folder is None:
        base_folder = os.path.dirname(header_json_path)
        if not base_folder:
            base_folder = "."  # current directory if no folder in path

    # ✅ Create subfolder 'headers' inside that domain folder
    headers_folder = os.path.join(base_folder, "headers")
    os.makedirs(headers_folder, exist_ok=True)

    # ✅ Load the header links JSON
    with open(header_json_path, "r", encoding="utf-8") as f:
        headers = json.load(f)

    # Handle invalid data
    if isinstance(headers, dict) and "raw_text" in headers:
        print("⚠️ Warning: The file contains raw text instead of valid JSON.")
        return

    all_links = {}

    # ✅ Loop through each header entry
    for header in headers:
        url = header.get("href")
        text = header.get("text") or "Untitled"

        if not url:
            print(f"⚠️ Skipping header without URL: {text}")
            continue

        safe_name = sanitize_filename(text.lower())
        output_file = os.path.join(headers_folder, f"{safe_name}.json")

        print(f"\n🌐 Extracting links from: {url} ({text})")

        try:
            links = extract_links(url)
            all_links[text] = links

            # ✅ Save extracted links to headers folder inside the same domain folder
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(links, f, indent=2, ensure_ascii=False)

            print(f"✅ Saved {len(links)} links → {output_file}")

        except Exception as e:
            print(f"❌ Failed to extract from {url}: {e}")

    print(f"\n✅ Extraction complete! All header links saved inside '{headers_folder}/'")
    print(f"📄 Total pages processed: {len(all_links)}")

    return all_links



if __name__ == "__main__":
    header_json_path="comp360software/header_links.json"
    base_folder="comp360software"
    extract_links_from_header_json(header_json_path, base_folder)
