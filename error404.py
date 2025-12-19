import requests
from playwright.sync_api import sync_playwright
import os
 
def screenshot_if_404(
    url,
    base_folder,
    initial_wait=1,     # wait after page load (seconds)
    scroll_rounds=8,     # how many scroll cycles
    scroll_wait=2,       # wait between scrolls (seconds)
    final_wait=10        # wait before screenshot (seconds)
):
    try:
        input_mm=os.path.join(base_folder,"Full_Website_Structure_updated_with_descriptions_and_testCases.mm")
        output_file=os.path.join(base_folder,"screenshot","404_screenshot.png")
        screenshot=os.path.join("screenshot","404_screenshot.png")
        # Step 1: Check HTTP status
        response = requests.get(url, timeout=30, allow_redirects=True)
 
        if response.status_code != 404:
            print(f"URL is NOT 404 (status: {response.status_code})")
            return
 
        print("404 detected, loading page slowly...")
 
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
 
            # Step 2: Safe navigation (no networkidle)
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(15000)  
 
            # Step 3: Long initial wait
            page.wait_for_timeout(initial_wait * 1000)
 
            # Step 4: Scroll to trigger lazy loading
            page.evaluate(f"""
                async () => {{
                    for (let i = 0; i < {scroll_rounds}; i++) {{
                        window.scrollBy(0, document.body.scrollHeight);
                        await new Promise(r => setTimeout(r, {scroll_wait * 1000}));
                    }}
                }}
            """)
 
            # Step 5: Extra final wait (videos, ads, animations)
            page.wait_for_timeout(final_wait * 1000)
 
            # Step 6: Screenshot
            page.screenshot(path=output_file, full_page=True)
            browser.close()
        link_in_mm(input_mm,input_mm,screenshot)
        print(f"Screenshot saved as {output_file}")
 
    except requests.exceptions.RequestException as e:
        print("Request failed (not a 404):", e)
    
# Example (very slow page)
# screenshot_if_404(
#     "https://comp360software.com/abs",
#     initial_wait=15,
#     scroll_rounds=10,
#     scroll_wait=2,
#     final_wait=15
# )
def link_in_mm(input_mm, output_mm, screenshot, title="Error Page"):
    """
    Create a first-layer 'Error Page' node and attach a screenshot image to it.
    """
    import xml.etree.ElementTree as ET
    import os
    from datetime import datetime

    # Parse mindmap
    tree = ET.parse(input_mm)
    root = tree.getroot()

    # Get root node (first top-level node)
    parent_nodes = root.findall("./node")
    if not parent_nodes:
        raise ValueError("❌ No top-level <node> in mindmap.")

    root_node = parent_nodes[0]

    # Create error page node (first layer)
    error_node = ET.SubElement(
        root_node,
        "node",
        {
            "TEXT": title,
            "CREATED": str(int(datetime.now().timestamp() * 1000)),
            "MODIFIED": str(int(datetime.now().timestamp() * 1000))
        }
    )

    # Attach screenshot via richcontent
    richcontent = ET.SubElement(error_node, "richcontent", {"TYPE": "NODE"})

    html = ET.SubElement(richcontent, "html")
    ET.SubElement(html, "head")
    body = ET.SubElement(html, "body")

    ET.SubElement(
        body,
        "img",
        {
            "src": screenshot,
            "alt": "404 Screenshot",
            "width": "500",
            "height": "250"
        }
    )

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_mm), exist_ok=True)

    # Save file
    tree.write(output_mm, encoding="utf-8", xml_declaration=True)

    print("✅ Error node created and screenshot attached")

if __name__ == "__main__":
    input_mm = r"comp360software\Full_Website_Structure_updated_with_descriptions_and_testCases.mm"
    output_mm = r"comp360software\Full_Website_Structure_updated_with_descriptions_and_testCases_and_screenshot.mm"
    screenshot_full= r"comp360software\screenshot\404_screenshot.png"
    screenshot = r"screenshot\404_screenshot.png"
    base_folder="comp360software"
    screenshot_if_404("https://comp360software.com/abs",base_folder=base_folder)
    # link_in_mm(input_mm, output_mm, screenshot)

