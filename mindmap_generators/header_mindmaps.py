"""
Header-based pages → chunked screenshots → multi-stage GPT → FreeMind mindmaps
"""
import os
import re
import json
import time
import math
import textwrap
import base64
from io import BytesIO
from typing import List, Dict
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from openai import OpenAI
from opik import configure as opik_configure
from opik.integrations.openai import track_openai
from PIL import Image
import asyncio
from playwright.async_api import async_playwright

# Optional tiktoken for token counting
try:
    import tiktoken
    from tiktoken import encoding_for_model
    TIKTOKEN_AVAILABLE = True
except Exception:
    TIKTOKEN_AVAILABLE = False

# -------------------------
# CONFIG
# -------------------------
MAX_INPUT_TOKENS = 1_000_000
CHUNK_MODEL = "gpt-4.1"
FINAL_MODEL = "gpt-4.1"
IMAGE_TOKEN_OVERHEAD = 85
IMAGE_BYTES_PER_TOKEN = 771
COMPRESS_IMAGES = True
COMPRESS_MAX_WIDTH = 1200
TRUNCATE_PREV_TOKENS = 200000

# -------------------------
# Utilities
# -------------------------
def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def configure_openai_with_opik() -> OpenAI:
    load_dotenv()
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not found in environment.")
    opik_configure()
    client = OpenAI(api_key=key)
    return track_openai(client)

# -------------------------
# Images
# -------------------------
def compress_image_to_base64(path: str, max_width: int = COMPRESS_MAX_WIDTH) -> str:
    with Image.open(path) as img:
        if img.width > max_width:
            ratio = max_width / float(img.width)
            img = img.resize((max_width, int(img.height * ratio)), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True)
        return base64.b64encode(buf.getvalue()).decode("utf-8")

def load_images_as_base64(folder_path: str, compress: bool = COMPRESS_IMAGES) -> List[Dict]:
    valid_ext = {".png", ".jpg", ".jpeg", ".webp"}
    imgs = []
    for filename in sorted(os.listdir(folder_path)):
        if not any(filename.lower().endswith(e) for e in valid_ext):
            continue
        fp = os.path.join(folder_path, filename)
        if compress:
            b64 = compress_image_to_base64(fp)
            raw_bytes = base64.b64decode(b64)
        else:
            with open(fp, "rb") as fh:
                raw = fh.read()
            b64 = base64.b64encode(raw).decode("utf-8")
            raw_bytes = raw
        imgs.append({"filename": filename, "base64": b64, "bytes_len": len(raw_bytes), "path": fp})
    return imgs

def estimate_image_tokens_from_bytes(image_bytes_len: int) -> int:
    return IMAGE_TOKEN_OVERHEAD + (image_bytes_len // IMAGE_BYTES_PER_TOKEN)

def count_text_tokens_for_model(model: str, text: str) -> int:
    if TIKTOKEN_AVAILABLE:
        try:
            enc = encoding_for_model(model)
            return len(enc.encode(text))
        except Exception:
            pass
    return max(1, len(text) // 4)

def chunk_images_by_token_limit(model: str, prompt_text: str, images: List[Dict], max_tokens: int = MAX_INPUT_TOKENS) -> List[List[Dict]]:
    batches = []
    current_batch = []
    current_tokens = count_text_tokens_for_model(model, prompt_text)
    for img in images:
        img_tokens = estimate_image_tokens_from_bytes(img["bytes_len"])
        if current_tokens + img_tokens > max_tokens:
            if current_batch:
                batches.append(current_batch)
            current_batch = [img]
            current_tokens = count_text_tokens_for_model(model, prompt_text) + img_tokens
            if current_tokens > max_tokens:
                print(f"⚠️ Single image '{img['filename']}' exceeds token limit ({current_tokens})")
                batches.append(current_batch)
                current_batch = []
                current_tokens = count_text_tokens_for_model(model, prompt_text)
        else:
            current_batch.append(img)
            current_tokens += img_tokens
    if current_batch:
        batches.append(current_batch)
    return batches

def build_messages(prompt_text: str, previous_output: str, images_batch: List[Dict]) -> list:
    content_items = [{"type": "text", "text": prompt_text}]
    if previous_output:
        content_items.append({"type": "text", "text": previous_output})
    for img in images_batch:
        content_items.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img['base64']}"}})
    return [
        {"role": "system", "content": "You are an expert in website information architecture and FreeMind XML."},
        {"role": "user", "content": content_items},
    ]

def truncate_text_to_token_budget(model: str, text: str, token_budget: int) -> str:
    if not text:
        return ""
    if TIKTOKEN_AVAILABLE:
        try:
            enc = encoding_for_model(model)
            tokens = enc.encode(text)
            if len(tokens) <= token_budget:
                return text
            return enc.decode(tokens[-token_budget:])
        except Exception:
            pass
    return text[-token_budget*4:]

async def take_chunked_screenshots(url, page_name, screenshot_folder, chunk_height=2000):
    os.makedirs(screenshot_folder, exist_ok=True)
    os.makedirs(os.path.join(screenshot_folder, page_name), exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": chunk_height})

        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(5)

        # Always get dynamic height
        total_height = await page.evaluate("document.body.scrollHeight")
        print(f"[INFO] Total height detected: {total_height}")

        chunk_paths = []
        y = 0
        idx = 1

        while y < total_height:
            print(f"[INFO] Scrolling to y={y}")

            # Scroll to position
            await page.evaluate(f"window.scrollTo(0, {y})")
            await page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(0.5)
            await page.mouse.move(100, 100)
            await page.mouse.move(120, 120)
            await asyncio.sleep(1)
            # 🔥 TAKE NORMAL VIEWPORT SCREENSHOT (NO CLIP!)
            out_path = os.path.join(screenshot_folder, page_name, f"chunk_{idx}.png")
            print(f"[INFO] Screenshot chunk {idx}")

            await page.screenshot(path=out_path, full_page=False)
            chunk_paths.append(out_path)

            y += chunk_height
            idx += 1

            # Recalculate height each time (lazy-load support)
            total_height = await page.evaluate("document.body.scrollHeight")

        await browser.close()
        return chunk_paths

# -------------------------
# Multi-stage orchestrator
# -------------------------
def multi_stage_mindmap_generation(client, model: str, prompt_text: str, images: List[Dict], output_file: str) -> str:
    batches = chunk_images_by_token_limit(model, prompt_text, images, MAX_INPUT_TOKENS)
    previous_output = ""
    final_output = None
    for idx, batch in enumerate(batches, start=1):
        prev_for_call = truncate_text_to_token_budget(model, previous_output, TRUNCATE_PREV_TOKENS) if previous_output else ""
        messages = build_messages(prompt_text, prev_for_call, batch)
        resp = client.chat.completions.create(model=model, messages=messages)
        msg_text = resp.choices[0].message.content.strip()
        previous_output = msg_text
        final_output = msg_text
    if not final_output:
        raise RuntimeError("No output from GPT")
    start = final_output.find("<map")
    if start == -1:
        with open(output_file+".raw.txt","w",encoding="utf-8") as fh:
            fh.write(final_output)
        raise ValueError("Output missing <map> XML; raw saved.")
    mm_xml = final_output[start:]
    if mm_xml.endswith("```"):
        mm_xml = mm_xml[:-3].strip()
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file,"w",encoding="utf-8") as fh:
        fh.write(mm_xml)
    return output_file

# -------------------------
# Prompt builder
# -------------------------
def build_mindmap_prompt(page_name: str, all_links: List[Dict]) -> str:
    if page_name.lower() in ["home", "homepage"]:
        return None
    return textwrap.dedent(f"""
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
                {json.dumps(all_links, indent=2)}
            - Skip duplicate or irrelevant links.
            8. Every visible major section of the webpage should be represented as a main node.
            9. Each node must be enriched with relevant **links**, **buttons**, and **form fields** 
            based on the provided data and visible content.
        🧩  Output Formatting Rules
            Output only valid FreeMind XML — no markdown, explanations, or comments.

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

            Accurately extract and represent all visible, meaningful, and interactive elements of the page content.

            Exclude any part of the header or footer.

            Return only the valid .mm XML output.
            
    """).strip()

def replace_ampersand_with_space(input_file, output_file=None):
    """
    Replace '&' with a space in all node TEXT attributes inside a FreeMind (.mm) file,
    even if the XML has unescaped ampersands.
    """
    if not os.path.exists(input_file):
        print(f"❌ File not found: {input_file}")
        return

    if output_file is None:
        output_file = input_file

    # 🔧 Read raw text and fix invalid '&' before parsing
    with open(input_file, "r", encoding="utf-8") as f:
        xml_text = f.read()

    # Replace only ampersands that are NOT part of &amp;, &lt;, etc.
    xml_text = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;)', '&amp;', xml_text)

    # Parse the fixed XML
    root = ET.fromstring(xml_text)

    count = 0
    for node in root.iter("node"):
        text = node.get("TEXT")
        if text and "&" in text:
            print(f"replacing {text}")
            new_text = text.replace("&", " ")
            node.set("TEXT", new_text)
            count += 1

    tree = ET.ElementTree(root)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"✅ Replaced '&' with spaces in {count} nodes → {output_file}")


# -------------------------
# Page processor
# -------------------------
async def process_page(client, page_name: str, page_url: str, all_links: List[Dict],
                       screenshot_folder: str = "screenshot", output_folder: str = "mindmaps"):
    print(f"\n=== Processing page: {page_name} → {page_url} ===")
    chunk_paths = await take_chunked_screenshots(page_url, page_name, screenshot_folder)
    images = []
    for cp in chunk_paths:
        imgs = load_images_as_base64(os.path.dirname(cp), compress=True)
        images.extend([i for i in imgs if os.path.abspath(i["path"]) == os.path.abspath(cp)])
    if not images:
        print(f"⚠️ No images for {page_name}")
        return None
    prompt = build_mindmap_prompt(page_name, all_links)
    output_file = os.path.join(output_folder, f"{page_name}.mm")
    try:
        multi_stage_mindmap_generation(client, CHUNK_MODEL, prompt, images, output_file)
        replace_ampersand_with_space(output_file,output_file)
        print(f"✅ Mindmap saved: {output_file}")
        return output_file
    except Exception as e:
        print(f"❌ Failed for {page_name}: {e}")
        return None

# -------------------------
# Main orchestrator
# -------------------------
async def generate_mindmaps_from_headers(headers_folder=r"comp360software\headers",
                                         extracted_headers_path=r"comp360software\header_links.json",
                                         output_folder=r"comp360software\mindmaps",
                                         screenshot_folder=r"comp360software\screenshot"):
    client = configure_openai_with_opik()
    os.makedirs(output_folder, exist_ok=True)
    os.makedirs(screenshot_folder, exist_ok=True)

    if not os.path.exists(headers_folder) or not os.path.exists(extracted_headers_path):
        print("❌ Headers folder or header_links.json not found.")
        return

    with open(extracted_headers_path,"r",encoding="utf-8") as fh:
        header_data = json.load(fh)
    header_url_map = {normalize_text(item["text"]): item["href"] for item in header_data if "href" in item}

    for header_file in sorted(os.listdir(headers_folder)):
        if not header_file.lower().endswith(".json"):
            continue
        page_name = os.path.splitext(header_file)[0]
        with open(os.path.join(headers_folder, header_file),"r",encoding="utf-8") as fh:
            all_links = json.load(fh)
        if not all_links:
            continue
        page_url = header_url_map.get(normalize_text(page_name))
        if not page_url:
            continue
        await process_page(client, page_name, page_url, all_links, screenshot_folder, output_folder)

    print("\n✅ All pages processed.")

# -------------------------
# Entrypoint
# -------------------------
if __name__ == "__main__":
    try:
        asyncio.run(generate_mindmaps_from_headers())
    except KeyboardInterrupt:
        print("Interrupted by user")
