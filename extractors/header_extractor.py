from playwright.sync_api import sync_playwright, TimeoutError
import json
import os
import math
from urllib.parse import urljoin

def clean_title(text):
    """
    Keep only the first line before any newline or extra whitespace.
    """
    if not text:
        return text
    # Split at newline and strip extra spaces
    return text.split('\n')[0].strip()

def process_json(input_file, output_file):
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cleaned_data = []
    seen = set()  # To track duplicates (text, href)

    for item in data:
        clean_text = clean_title(item.get('text', ''))
        href = item.get('href', '')
        key = (clean_text, href)

        # Skip duplicates
        if key not in seen:
            seen.add(key)
            cleaned_data.append({
                "text": clean_text,
                "href": href
            })

    # Save cleaned JSON
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, indent=2, ensure_ascii=False)

    print(f"Cleaned JSON saved to {output_file}")


def extract_header_links(url, headless=False, output_file="header_links.json"):
    """
    Extract header navigation + submenu links.
    Converts all relative URLs to absolute URLs automatically.
    """

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        all_links = []

        # -----------------------------------------------------
        # 1. Try to locate a header or primary nav container
        # -----------------------------------------------------
        container = page.locator("header")

        if container.count() == 0:
            container = page.locator("nav, div.navbar, div.menu, div.customuseful_links")

        if container.count() == 0:
            print("⚠️ No header/nav found — using full body link scan")
            container = None
        else:
            container = container.first

        # -----------------------------------------------------
        # 2. Extract top-level links
        # -----------------------------------------------------
        if container:
            top_links = container.locator("a[href]")
        else:
            top_links = page.locator("body a[href]")

        for link in top_links.all():
            try:
                text = link.inner_text().strip()
                href = link.get_attribute("href")

                if not href or not text:
                    continue

                # Skip useless links
                if href.startswith(("javascript:", "mailto:", "tel:")):
                    continue
                if href == "#" or href.endswith("#"):
                    continue
                
                # Convert to absolute URL
                href = urljoin(url, href.strip())

                all_links.append({"text": text, "href": href})

            except:
                pass

        # -----------------------------------------------------
        # 3. Extract dropdown submenu links
        # -----------------------------------------------------
        if container:
            menu_items = container.locator("nav a, li > a, li > button").all()

            for item in menu_items:
                try:
                    item.hover(timeout=1500)
                except:
                    continue

                dropdown = item.locator(
                    """
                    xpath=ancestor::li//*[self::ul or self::div][
                        contains(@class, 'menu') or
                        contains(@class, 'dropdown') or
                        contains(@class, 'sub') or
                        contains(@class, 'mega')
                    ]
                    """
                )

                if dropdown.count() == 0:
                    continue

                dd = dropdown.first

                try:
                    dd.wait_for(state="visible", timeout=1000)
                except:
                    continue

                submenu_links = dd.locator("a[href]").all()

                for sl in submenu_links:
                    try:
                        text = sl.inner_text().strip()
                        href = sl.get_attribute("href")

                        if not href or not text:
                            continue
                        if href.startswith(("javascript:", "mailto:", "tel:")):
                            continue
                        if href == "#" or href.endswith("#"):
                            continue

                        # Convert to absolute
                        href = urljoin(url, href.strip())

                        all_links.append({"text": text, "href": href})

                    except:
                        pass

        # -----------------------------------------------------
        # 4. Deduplicate (case-insensitive for text)
        # -----------------------------------------------------
        cleaned = []
        seen = set()

        for link in all_links:
            text = link["text"].strip()
            href = link["href"].strip()

            # Case-insensitive text dedupe + absolute HREF dedupe
            key = (text.lower(), href.rstrip("/").lower())

            if key in seen:
                continue

            seen.add(key)
            cleaned.append({"text": text, "href": href})

        # -----------------------------------------------------
        # 5. Save Output
        # -----------------------------------------------------
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(cleaned, f, indent=2, ensure_ascii=False)

        print(f"✅ Done. Extracted {len(cleaned)} links.")
        process_json(output_file,output_file)
        return output_file


from PIL import Image
import os
import math
from playwright.sync_api import sync_playwright

def home_screenshot(url, output_folder):
    partition_height = 1500
    scroll_increment = 400
    scroll_pause = 0.2  # seconds

    os.makedirs(output_folder, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(url, wait_until="domcontentloaded", timeout=60000)

        # Remove sticky/fixed elements
        page.evaluate("""
        () => {
            document.querySelectorAll('*').forEach(el => {
                const style = window.getComputedStyle(el);
                if (style.position === 'fixed' || style.position === 'sticky') {
                    el.style.position = 'static';
                    el.style.top = 'auto';
                    el.style.bottom = 'auto';
                    el.style.zIndex = '0';
                }
            });
        }
        """)

        # -------------------------
        # Scroll slowly to load lazy content
        # -------------------------
        total_height = page.evaluate("document.body.scrollHeight")
        print(f"📏 Total page height: {total_height}px")

        for y in range(0, total_height, scroll_increment):
            page.evaluate(f"window.scrollTo(0, {y})")
            page.wait_for_timeout(int(scroll_pause * 1000))

        # Final scroll to bottom to trigger lazy loading
        page.evaluate(f"window.scrollTo(0, {total_height})")
        page.wait_for_timeout(6000)

        # -------------------------
        # Take partitioned screenshots
        # -------------------------
        page_width = page.evaluate("document.body.scrollWidth")
        num_screens = math.ceil(total_height / partition_height)
        print(f"🖼 Number of screenshots: {num_screens}")

        for i in range(num_screens):
            top = i * partition_height
            height = min(partition_height, total_height - top)

            page.set_viewport_size({
                "width": page_width,
                "height": height
            })

            page.evaluate(f"window.scrollTo(0, {top})")

            # Wait to allow animations to play
            page.wait_for_timeout(10000)  # 1 second; adjust if animations are slow
            page.mouse.move(100, 100)
            page.mouse.move(120, 120)
            page.wait_for_timeout(500)
            file_path = os.path.join(output_folder, f"image_{i+1}.png")
            page.screenshot(path=file_path)  # animations are preserved
            print(f"✅ Saved: {file_path}")

        browser.close()
if __name__ == "__main__":
    target_url = "https://dmaid.dk/"
    output_folder = r"dmaid\screenshot\home"
    links_file = extract_header_links(target_url, headless=False,output_file=r"dmaid\header_links.json")
    home_screenshot(target_url, output_folder)

    if links_file:
        print(f"\n🎉 Process complete. Check the file: {links_file}")
    else:
        print("\n🚫 Process finished without creating a file.")
    
        # https://www.340bpriceguide.net/
        # https://dayzee.com/
        # https://kidneycareconsultants.com/
        # https://lionsandtigers.com/
        # https://nutriwest.com/
        # https://www.genetechsolutions.com/