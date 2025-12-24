import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import os 

def load_session_from_auth_state(auth_file="auth_state.json"):
    """Load cookies or headers from saved auth state"""
    with open(auth_file, "r", encoding="utf-8") as f:
        auth = json.load(f)

    session = requests.Session()

    # If cookies exist, set them
    if "cookies" in auth:
        for cookie in auth["cookies"]:
            session.cookies.set(cookie["name"], cookie["value"])

    # If headers (like Authorization tokens) exist
    if "headers" in auth:
        session.headers.update(auth["headers"])

    return session


def extract_links(session, url):
    """Extract all links with page title and anchor text from the authenticated page"""
    response = session.get(url, timeout=10)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    page_title = soup.title.string.strip() if soup.title else "No Title"

    links_data = []
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"])
        text = a.get_text(strip=True)

        if href and text:
            links_data.append({
                "page_title": page_title,
                "hyper_text": text,
                "link": href
            })

    print(f"✅ Found {len(links_data)} links on {url}")
    return links_data

async def extract_home_link(AUTH_STATE,target_url,home_path):
    if not os.path.exists(AUTH_STATE):
        print("\n❌ auth_state.json not found!")
        print("Run login script once to generate it.\n")
        return
    session = load_session_from_auth_state(AUTH_STATE)
    links = extract_links(session, target_url)
    with open(home_path, "w", encoding="utf-8") as f:
        json.dump(links, f, indent=2)
    
    print("✅ Saved authenticated link data to home_page_links_after_login.json")


# if __name__ == "__main__":
#     # Load authenticated session
#     session = load_session_from_auth_state("auth_state.json")

#     # URL to extract after login
#     target_url = "https://www.340bpriceguide.net/"

#     links = extract_links(session, target_url)

#     # Save to new file
#     with open("home_page_links_after_login.json", "w", encoding="utf-8") as f:
#         json.dump(links, f, indent=2)

#     print("✅ Saved authenticated link data to home_page_links_after_login.json")
