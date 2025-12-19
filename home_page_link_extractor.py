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



if __name__ == "__main__":
    links=extract_links("https://dmaid.dk/")
    with open(r"dmaid/home_page_links.json", "w", encoding="utf-8") as f:
        json.dump(links, f, indent=2)
