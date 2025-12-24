import os
import json
import re
import asyncio
from playwright.async_api import async_playwright

# === CONFIG ===
AUTH_STATE = "auth_state.json"
HEADERS_FOLDER = "headers_After_Login"




# Utility: remove duplicate links
def dedupe_links(links):
    seen = set()
    unique = []
    for l in links:
        href = l.get("href")
        if href and href not in seen:
            seen.add(href)
            unique.append(l)
    return unique


# === MAIN (SKIP LOGIN USING SAVED SESSION) ===
async def extract_header_links_and_screenshots(url,AUTH_STATE,HEADERS_FOLDER):
    os.makedirs(HEADERS_FOLDER, exist_ok=True)
    if not os.path.exists(AUTH_STATE):
        print("\n❌ auth_state.json not found!")
        print("Run login script once to generate it.\n")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=AUTH_STATE)
        page = await context.new_page()

        print("Using saved session... skipping login!")

        # Go to home/dashboard
        await page.goto(url, timeout=60000)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(5)

        print("\n🔍 Extracting visible header links...")

        # Step 1: Get visible header links
        header_links = await page.eval_on_selector_all(
            "header a, nav a, .nav a, .navbar a",
            """els => els
                .map(a => ({ text: a.innerText.trim(), href: a.href }))
                .filter(l => l.text && l.href && !l.href.startsWith("javascript"))
            """
        )

        print(f"Top-level header links: {len(header_links)}")

        all_links = header_links.copy()

        # Step 2: Extract submenu links by hovering parent <li>
        print("\n🔍 Scanning for dropdown / submenu items...")

        menu_parents = page.locator(
            "li:has(ul), li:has(ul.sub-menu), li:has(div.sub-menu)"
        )

        parent_count = await menu_parents.count()
        print(f"Found {parent_count} possible dropdown parent items")

        for i in range(parent_count):
            parent = menu_parents.nth(i)
            try:
                await parent.hover()
                await asyncio.sleep(0.5)

                submenu_links = await parent.eval_on_selector_all(
                    "a[href]",
                    """els => els
                        .map(a => ({ text: a.innerText.trim(), href: a.href }))
                        .filter(x => x.text && x.href && !x.href.startsWith("javascript"))
                    """
                )

                if submenu_links:
                    print(f"  ➤ Found {len(submenu_links)} submenu links")
                    all_links.extend(submenu_links)

            except Exception as e:
                print(f"  ⚠️ Submenu hover failed: {e}")

        # Deduplicate all header + submenu links
        all_links = dedupe_links(all_links)

        # Save final header links
        with open("header_links_After_Login.json", "w", encoding="utf-8") as f:
            json.dump(all_links, f, indent=2, ensure_ascii=False)

        print(f"\n✅ Total header + submenu links saved: {len(all_links)}")

        # Step 3: Visit each header link
        for link in all_links:
            name = re.sub(r"[^\w]", "_", link["text"])
            url = link["href"]
            if link['text']=="Logout":
                continue
            print(f"\n🌐 Visiting: {link['text']} → {url}")

            try:
                await page.goto(url, wait_until="networkidle", timeout=50000)
                await asyncio.sleep(5)

                # Extract all links from the page
                page_links = await page.eval_on_selector_all(
                    "a[href]",
                    """els => els
                        .map(a => ({ text: a.innerText.trim(), href: a.href }))
                        .filter(l => l.text && l.href)
                    """
                )

                json_path = os.path.join(HEADERS_FOLDER, f"{name}.json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(page_links, f, indent=2, ensure_ascii=False)

                print(f"   ➤ Saved {len(page_links)} links → {name}.json")

            except Exception as e:
                print(f"   ❌ Failed to load {url}: {e}")

        await browser.close()

    print("\n🎉 ALL DONE — Full header + submenu extraction complete!")


if __name__ == "__main__":
    asyncio.run(extract_header_links_and_screenshots())