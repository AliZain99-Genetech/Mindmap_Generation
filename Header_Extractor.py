import json
import asyncio
from playwright.async_api import async_playwright # type: ignore
import os
from domain_extractor import extract_domain  # Make sure this exist

async def extract_header_links(url, folder_name, headless=True):
    """Extract header links and return them"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, slow_mo=200)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # Extract header links
            links = await page.eval_on_selector_all(
                "header a",
                "els => els.map(e => ({text: e.innerText.trim(), href: e.href}))"
            )

            # ---- Save JSON file inside the folder ----
            json_file_path = os.path.join(folder_name, "header_links.json")

            with open(json_file_path, "w", encoding="utf-8") as f:
                json.dump(links, f, indent=2, ensure_ascii=False)

            print(f"✅ Extracted {len(links)} header links.")
            print(f"💾 Saved to: {json_file_path}")

            return links

        except Exception as e:
            print(f"❌ Error extracting links: {str(e)}")
            raise

        finally:
            await browser.close()


def clean_header_links(input_file, output_file):
    """Clean header links by removing empty entries and duplicates"""
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            links = json.load(f)
        
        # Remove empty entries
        cleaned = [link for link in links if link.get("href") and link.get("text")]
        
        # Remove duplicates based on href only (keep first occurrence)
        seen_hrefs = set()
        unique_links = []
        for link in cleaned:
            if link["href"] not in seen_hrefs:
                seen_hrefs.add(link["href"])
                unique_links.append(link)
        
        # Save cleaned and deduplicated links
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(unique_links, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Cleaned: {len(links)} → {len(unique_links)} unique links")
        return unique_links
        
    except Exception as e:
        print(f"Error cleaning links: {str(e)}")
        raise

# if __name__ == "__main__":
#     url = "https://nutriwest.com/"
#     asyncio.run(extract_header_links(url, headless=False))
#     clean_header_links("header_links.json", "header_links.json")