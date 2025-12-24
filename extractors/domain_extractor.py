
import re

def extract_domain(url):
    # Extract domain part first (e.g., 'www.example.com')
    pattern = r'^(?:https?:\/\/)?(?:www\.)?([^\/:]+)'
    match = re.search(pattern, url)
    if not match:
        return None

    domain = match.group(1)  # e.g., 'sub.domain.co.uk' or 'example.com'

    # Split domain into parts
    parts = domain.split('.')
    if len(parts) >= 2:
        # Handle cases like sub.domain.co.uk or www.example.com
        # Return the second last part (main domain)
        return parts[-2]
    else:
        # For edge cases like localhost or IPs
        return parts[0]

# Example usage
urls = [
    "https://www.example.com/path/page",
    "http://sub.domain.co.uk/test",
    "www.google.com/search?q=test",
    "https://340bpriceguide.net",
    "ftp://example.org/resource",
    "https://lionsandtigers.com/",
    "https://lionsandtigers.com"
]

for u in urls:
    print(f"URL: {u}  →  Middle name: {extract_domain(u)}")
