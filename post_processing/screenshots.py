import os
import re
import asyncio
import xml.etree.ElementTree as ET
from playwright.async_api import async_playwright # type: ignore

# === CONFIG ===
VIEWPORT_WIDTH = 1920     # ← change to your laptop screen width
VIEWPORT_HEIGHT = 1080    # ← change to your laptop screen height


def safe_filename(url: str) -> str:
    """Sanitize URL to create a valid Windows filename."""
    safe = re.sub(r"[<>:\"/\\|?*=&#%@]", "_", url)
    safe = re.sub(r"_+", "_", safe).strip("_")
    return safe[:150]


async def take_screenshot(url: str, filename: str):
    """Capture screenshot at laptop viewport size."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            ignore_https_errors=True,
            viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT}
        )
        page = await context.new_page()
        try:
            await page.goto(url,wait_until="domcontentloaded", timeout=90000)
            await asyncio.sleep(2)  # small delay to ensure page loads fully # 1 second; adjust if animations are slow
            await page.mouse.move(100, 100)
            await page.mouse.move(120, 120)
            await page.wait_for_timeout(500)
            await page.screenshot(path=filename)  # not full_page
            print(f"✅ Screenshot captured for {url}")
        except Exception as e:
            print(f"❌ Failed {url}: {e}")
        await browser.close()


def add_screenshot_node(parent_node, screenshot_path):
    """Add a <node> child containing rich HTML with a self-closed <img> tag."""
    # Avoid adding duplicate screenshot nodes
    for child in parent_node.findall("node"):
        if child.get("TEXT") == "Screenshot Example":
            return

    node = ET.Element("node")
    node.set("TEXT", "Screenshot Example")

    rich = ET.SubElement(node, "richcontent")
    rich.set("TYPE", "NODE")

    # Manually build XHTML-compliant string to ensure proper <img /> closure
    screenshot_url = screenshot_path.replace("\\", "/")

    html_str = f"""
    <html>
    <body>
        <p>
        <img src="{screenshot_url}" width="500" height="250"/>
        </p>
    </body>
    </html>
    """.strip()


    # Parse string as XML fragment (so img is properly self-closed)
    html_elem = ET.fromstring(html_str)
    rich.append(html_elem)

    parent_node.append(node)


async def Screenshot_Node(base_folder="."):
    INPUT_MM = os.path.join(base_folder, "Merged_Website_Structure.mm")
    OUTPUT_MM = os.path.join(base_folder, "Full_Website_Structure_with_screenshots.mm")
    SCREENSHOT_DIR = os.path.join(base_folder, "hyperlink_screenshots")
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    tree = ET.parse(INPUT_MM)
    root = tree.getroot()

    for node in root.iter("node"):
        link = node.get("LINK")
        if link and link.startswith(("http://", "https://")):
            safe_name = safe_filename(link)
            screenshot_path = os.path.join(SCREENSHOT_DIR, f"{safe_name}.png")
            relative_path = os.path.join(os.path.basename(SCREENSHOT_DIR), f"{safe_name}.png").replace("\\", "/")


            # Skip screenshot if it already exists
            if os.path.exists(screenshot_path):
                print(f"⏩ Skipping existing screenshot: {screenshot_path}")
            else:
                await take_screenshot(link, screenshot_path)

            # Always add screenshot node if not present
            add_screenshot_node(node, relative_path)

    tree.write(OUTPUT_MM, encoding="utf-8", xml_declaration=True)
    print(f"\n💾 Updated mindmap saved as: {OUTPUT_MM}")

async def Screenshot(base_folder="dayzee"):
    INPUT_MM = os.path.join(base_folder, "Full_Website_Structure_updated.mm")
    OUTPUT_MM = os.path.join(base_folder, "Full_Website_Structure_with_screenshots.mm")
    SCREENSHOT_DIR = os.path.join(base_folder, "hyperlink_screenshots")
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    tree = ET.parse(INPUT_MM)
    root = tree.getroot()

    for node in root.iter("node"):
        link = node.get("LINK")
        if link and link.startswith(("http://", "https://")):
            safe_name = safe_filename(link)
            screenshot_path = os.path.join(SCREENSHOT_DIR, f"{safe_name}.png")
            relative_path = os.path.join(os.path.basename(SCREENSHOT_DIR), f"{safe_name}.png").replace("\\", "/")


            # Skip screenshot if it already exists
            if os.path.exists(screenshot_path):
                print(f"⏩ Skipping existing screenshot: {screenshot_path}")
            else:
                await take_screenshot(link, screenshot_path)

            # Always add screenshot node if not present
            add_screenshot_node(node, relative_path)

    tree.write(OUTPUT_MM, encoding="utf-8", xml_declaration=True)
    print(f"\n💾 Updated mindmap saved as: {OUTPUT_MM}")

# if __name__ == "__main__":
#     asyncio.run(Screenshot("comp360software"))
