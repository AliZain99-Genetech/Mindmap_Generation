
import os
import re
import json
import math
import textwrap
import asyncio
import base64
from io import BytesIO
from typing import List, Dict
from PIL import Image
from dotenv import load_dotenv
from openai import OpenAI
from playwright.async_api import async_playwright
from opik import configure as opik_configure
from opik.integrations.openai import track_openai

# -------------------------------
# CONFIGURATION
# -------------------------------
def configure_openai_with_opik() -> OpenAI:
    """Load .env, configure opik, create OpenAI client with key, and wrap with opik.track_openai()."""
    load_dotenv()
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set in environment (.env).")
    # init opik
    opik_configure()
    client = OpenAI(api_key=key)
    return track_openai(client)
AUTH_STATE = "auth_state.json"


client = configure_openai_with_opik()

MODEL = "gpt-4.1"  # or "gpt-4o", "gpt-4.1" when available
# MODEL = "gpt-4o-mini"  # cheaper & still excellent for this task

# HEADERS_FOLDER = "headers_After_Login"
# SCREENSHOT_FOLDER = "screenshots_After_Login"
# MINDMAP_FOLDER = "mindmaps_After_Login"


# GPT-4.1 Vision limits (as of Nov 2025)
MAX_INPUT_TOKENS = 1_000_000
IMAGE_TOKEN_OVERHEAD = 85
IMAGE_BYTES_PER_TOKEN = 771
COMPRESS_MAX_WIDTH = 1200
TRUNCATE_PREV_TOKENS_CHARS = 250_000  # safe for XML

# -------------------------------
# Utilities
# -------------------------------
def compress_image_to_base64(path: str) -> str:
    with Image.open(path) as img:
        if img.width > COMPRESS_MAX_WIDTH:
            ratio = COMPRESS_MAX_WIDTH / img.width
            img = img.resize((COMPRESS_MAX_WIDTH, int(img.height * ratio)), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode()

def load_images_as_base64(folder: str) -> List[Dict]:
    images = []
    for file in sorted(os.listdir(folder)):
        if file.lower().endswith(('.png', '.jpg', '.jpeg')):
            path = os.path.join(folder, file)
            images.append({
                "path": path,
                "filename": file,
                "base64": compress_image_to_base64(path)
            })
    return images

def estimate_image_tokens(b64_str: str) -> int:
    bytes_len = len(base64.b64decode(b64_str))
    return IMAGE_TOKEN_OVERHEAD + (bytes_len // IMAGE_BYTES_PER_TOKEN)

def chunk_images_by_tokens(images: List[Dict], prompt_tokens: int) -> List[List[Dict]]:
    batches = []
    current = []
    used = prompt_tokens

    for img in images:
        img_tokens = estimate_image_tokens(img["base64"])
        if used + img_tokens > MAX_INPUT_TOKENS:
            if current:
                batches.append(current)
            current = [img]
            used = prompt_tokens + img_tokens
            if img_tokens > MAX_INPUT_TOKENS:
                print(f"⚠️ Single image {img['filename']} too big, sending alone")
                batches.append([img])
                current = []
                used = prompt_tokens
        else:
            current.append(img)
            used += img_tokens
    if current:
        batches.append(current)
    return batches

def truncate_previous(xml: str) -> str:
    return xml[-TRUNCATE_PREV_TOKENS_CHARS:] if xml else ""

def fix_xml_entities(xml_text: str) -> str:
    xml_text = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;)', '&amp;', xml_text)
    return xml_text

# -------------------------------
# Playwright: Chunked Screenshots
# -------------------------------
async def take_chunked_screenshots(url: str, page_name: str,SCREENSHOT_FOLDER: str, height: int = 1600,):
    out_dir = os.path.join(SCREENSHOT_FOLDER, page_name)
    os.makedirs(out_dir, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=AUTH_STATE)
        page = await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=120000)
        await page.wait_for_timeout(3000)

        total_height = await page.evaluate("document.documentElement.scrollHeight")
        width = await page.evaluate("document.documentElement.scrollWidth")

        # Trigger lazy load
        for y in range(0, total_height, 600):
            await page.evaluate(f"window.scrollTo(0, {y})")
            await page.wait_for_timeout(200)

        paths = []
        chunks = math.ceil(total_height / height)
        for i in range(chunks):
            top = i * height
            h = min(height, total_height - top)
            await page.set_viewport_size({"width": width, "height": h})
            await page.evaluate(f"window.scrollTo(0, {top})")
            await page.wait_for_timeout(300)
            path = os.path.join(out_dir, f"chunk_{i+1:03d}.png")
            await page.screenshot(path=path)
            paths.append(path)
        await browser.close()

    print(f"   → {len(paths)} chunks captured")
    return paths

# -------------------------------
# Prompt
# -------------------------------
def build_prompt(page_name: str, links: List[Dict], is_home: bool, previous_xml: str = "") -> str:
    link_json = json.dumps(links, indent=2, ensure_ascii=False)
    prev_block = f"\nPrevious partial mindmap (continue and complete it):\n```xml\n{previous_xml}\n```" if previous_xml else ""

    if is_home:
        extra="This is a home page -> Include header, navigation bar and footer. "
    else:
        extra = "This is NOT the home page → COMPLETELY EXCLUDE header, navigation bar, and footer."

    prompt = f"""
You are an intelligent assistant specialized in generating structured, professional website mind maps
            in valid FreeMind (.mm) XML format.

            ### 🎯 Objective
            Analyze the provided webpage screenshot, context, and extracted links to create a clear, hierarchical mind map 
            that accurately represents the *page content and structure* of the website.

            The generated mind map will help visualize the layout, navigation, and interactive elements of the webpage.

            ---

            ### 🧭 Core Rules & Structure
            1. The **root node** must always be the page title: "{page_name}".
            2. **Exclude** all elements that belong to the **Header** or **Footer**.
            - Do not include header menus, site logos, navigation bars, or footer links.
            - Use the provided screenshot as a reference to visually identify and exclude these.
            3. Focus only on **page-specific visible content** (the body section).
            - Include meaningful text sections, visible links, content blocks, images, and widgets.
            - Don't include all content of text, only the main headings and sections summary in one line.
            - Don't use more then two nodes for content , if any link or buttonn is present in the visible section then use that as the new node text.
            - Make sure to make visible sections heading based on content inside it 
            - Don't duplicate it 
            4. The hierarchy should follow the logical layout of the page:
            - Page Title
                - Main Content
                - Visible Sections
                - Forms (if any)
                - Buttons (if any)
            5. **Forms**:
            - Represent each form as a node.
            - Add its fields (e.g., text inputs, dropdowns, submit buttons) as child nodes.
            6. **Buttons**:
            - Represent each button as a node.
            - Use the visible button text or function as its subnode.
            7. **Links**:
            - Only include links that exist in the provided list below:
                {json.dumps(links, indent=2)}
            - Skip duplicate or irrelevant links.
            🧩 Output Formatting Rules
            Output only valid FreeMind XML — no markdown, explanations, or comments.
            8- If the provided .mm file contains invalid XML special characters (like &, <, >, ", or '), replace them with their valid XML entity equivalents (&amp;, &lt;, &gt;, &quot;, &apos;) and return a well-formed FreeMind .mm XML file only
            The structure must begin with:

            xml
            Copy code
            <map version="1.0.1">
                <node TEXT="{page_name}">
                    ...
                </node>
            </map>
            All nodes must use proper indentation and XML escaping for special characters.

            Ensure the output is fully parsable by FreeMind or Freeplane (no syntax errors).

            🪄 Summary
            Your goal:

            Accurately extract and represent all visible, meaningful, and interactive elements of the page content, For text based content only summarize it in one line.

            Exclude any part of the header or footer.

            If the provided .mm file contains invalid XML special characters (like &, <, >, ", or '), replace them with their valid XML entity equivalents (&amp;, &lt;, &gt;, &quot;, &apos;) and return a well-formed FreeMind .mm XML file only
            - Properly escape XML entities (& → &amp;, etc.){prev_block}

            Return only the complete or continued .mm XML.
"""
    return textwrap.dedent(prompt).strip()

# -------------------------------
# Multi-stage GPT-4.1 Vision
# -------------------------------
async def generate_mindmap_gpt(page_name: str, chunk_paths: List[str], all_links: List[Dict],MINDMAP_FOLDER):
    folder = os.path.dirname(chunk_paths[0])
    images = load_images_as_base64(folder)
    is_home = page_name.lower() in {"home", "homepage", "dashboard"}

    prompt_text = build_prompt(page_name, all_links, is_home)
    prompt_tokens = len(prompt_text) // 4 + 500  # rough estimate

    batches = chunk_images_by_tokens(images, prompt_tokens)

    previous_xml = ""
    final_xml = ""

    for i, batch in enumerate(batches, 1):
        print(f"   → GPT batch {i}/{len(batches)} ({len(batch)} images)")

        messages = [
            {"role": "system", "content": "You are an expert in FreeMind XML and web structure."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": build_prompt(page_name, all_links, is_home, previous_xml)},
                ] + [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img['base64']}"}}
                    for img in batch
                ]
            }
        ]

        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            # temperature=0.0,
            max_tokens=8192
        )

        raw = resp.choices[0].message.content.strip()
        start = raw.find("<map")
        if start == -1:
            raise ValueError("No <map found in GPT output")
        xml = fix_xml_entities(raw[start:])
        if xml.endswith("```"): xml = xml[:-3].strip()

        final_xml = xml
        previous_xml = truncate_previous(xml)

    output_path = os.path.join(MINDMAP_FOLDER, f"{page_name}.mm")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_xml)

    print(f"   ✅ Mindmap saved: {output_path}")
    return output_path

# -------------------------------
# Main
# -------------------------------
async def ensure_folder_async(path):
    os.makedirs(path, exist_ok=True)
    for _ in range(5):
        if os.path.exists(path):
            return
        await asyncio.sleep(0.05)
    if not os.path.exists(path):
        raise RuntimeError(f"Folder could not be created: {path}")
    
async def header(base_url,HEADERS_FOLDER,SCREENSHOT_FOLDER,MINDMAP_FOLDER):
    print("🚀 GPT-4.1 After-Login Mindmap Generator (Chunked + Multi-stage)")
    os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)
    os.makedirs(MINDMAP_FOLDER, exist_ok=True)

    
    for file in sorted(f for f in os.listdir(HEADERS_FOLDER) if f.endswith(".json")):
        page_name = os.path.splitext(file)[0]
        header_path = os.path.join(HEADERS_FOLDER, file)

        with open(header_path, "r", encoding="utf-8") as f:
            links = json.load(f)

        # Guess URL from links
        url = base_url
        for link in links:
            href = link.get("href", "")
            if page_name.lower().replace(" ", "") in href.lower().replace(" ", ""):
                url = href if href.startswith("http") else base_url + href
                break

        # fallback to homepage
        if not url:
            url = base_url

        print(f"\n📄 {page_name} → {url}")
        height=1600
        await take_chunked_screenshots(url, page_name,SCREENSHOT_FOLDER)
        folder = os.path.join(SCREENSHOT_FOLDER, page_name)
        print(folder)
        await ensure_folder_async(folder)
        chunks = [os.path.join(folder, f) for f in sorted(os.listdir(folder)) if f.endswith(".png")]

        if chunks:
            await generate_mindmap_gpt(page_name, chunks, links,MINDMAP_FOLDER)

    print("\n🎉 All done! Mindmaps in:", MINDMAP_FOLDER)

# if __name__ == "__main__":
#     asyncio.run(header("https://www.340bpriceguide.net/",r"340bpriceguide\headers",r"340bpriceguide\screenshot",r"340bpriceguide\mindmaps_After_Login"))
#     os.makedirs(r"340bpriceguide\screenshot", exist_ok=True)
#     os.makedirs(r"340bpriceguide\mindmaps_After_Login", exist_ok=True)