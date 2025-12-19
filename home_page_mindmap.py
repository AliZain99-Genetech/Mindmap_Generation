import os
import json
import re
import base64
import math
import textwrap
from io import BytesIO
from typing import List, Dict, Tuple
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
from openai import OpenAI
from opik import configure as opik_configure
from opik.integrations.openai import track_openai
from PIL import Image
import time

# Optional token encoder (tiktoken). If not installed or fails for model, fallback to heuristic.
try:
    import tiktoken
    from tiktoken import encoding_for_model
    TIKTOKEN_AVAILABLE = True
except Exception:
    TIKTOKEN_AVAILABLE = False

# -------------------------
# CONFIG
# -------------------------
MAX_INPUT_TOKENS = 1_000_000  # per user requirement
DEFAULT_MODEL = "gpt-4.1"     # user requested model
IMAGE_TOKEN_OVERHEAD = 85     # baseline tokens per image (approx)
IMAGE_BYTES_PER_TOKEN = 771   # approximation used in earlier guidance

# -------------------------
# Utilities: OpenAI + Opik
# -------------------------
async def configure_openai_with_opik() -> OpenAI:
    """Load .env, configure opik, create OpenAI client with key, and wrap with opik.track_openai()."""
    load_dotenv()
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set in environment (.env).")
    # init opik
    opik_configure()
    client = OpenAI(api_key=key)
    return track_openai(client)

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
# Image helpers
# -------------------------
async def compress_image_to_base64(path: str, max_width: int = 1200, quality: int = 80) -> str:
    """Resize (keeping aspect ratio) and return base64-encoded PNG bytes as string."""
    with Image.open(path) as img:
        if img.width > max_width:
            ratio = max_width / float(img.width)
            new_size = (max_width, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        # Save to PNG buffer
        buf = BytesIO()
        img.save(buf, format="PNG", optimize=True, quality=quality)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
import asyncio
async def ensure_folder_exists(folder_path: str, retries: int = 5, delay: float = 0.1):
    """Wait until folder exists, retrying a few times in case of async creation or FS latency."""
    for _ in range(retries):
        if os.path.exists(folder_path):
            return
        time.sleep(delay)
        if not os.path.exists(folder_path):
            raise FileNotFoundError(f"Folder not found or could not be created: {folder_path}")

async def load_images_as_base64(folder_path: str, compress: bool = False, max_width: int = 1200) -> List[Dict]:
    """Load all supported images in folder and return list of dicts: {'filename','base64','bytes'}"""
    await ensure_folder_exists(folder_path)
    valid_ext = {".png", ".jpg", ".jpeg", ".webp"}
    imgs = []

    for filename in sorted(os.listdir(folder_path)):
        if not any(filename.lower().endswith(e) for e in valid_ext):
            continue
        fp = os.path.join(folder_path, filename)
        if compress:
            b64 =await compress_image_to_base64(fp, max_width=max_width)
            raw_bytes = base64.b64decode(b64)
        else:
            with open(fp, "rb") as fh:
                raw = fh.read()
            b64 = base64.b64encode(raw).decode("utf-8")
            raw_bytes = raw
        imgs.append({"filename": filename, "base64": b64, "bytes_len": len(raw_bytes)})
    print(f"📸 Loaded {len(imgs)} image(s) from {folder_path} (compress={compress})")
    return imgs

# -------------------------
# Token estimation helpers
# -------------------------
def estimate_image_tokens_from_bytes(image_bytes_len: int) -> int:
    """
    Heuristic: tokens_per_image ≈ IMAGE_TOKEN_OVERHEAD + (image_bytes / IMAGE_BYTES_PER_TOKEN)
    This is a rough estimate; actual internal accounting may differ.
    """
    return IMAGE_TOKEN_OVERHEAD + (image_bytes_len // IMAGE_BYTES_PER_TOKEN)

# def count_text_tokens_for_model(model: str, text: str) -> int:
#     """Use tiktoken when possible, otherwise fallback to a heuristic (1 token per 4 chars)."""
#     if TIKTOKEN_AVAILABLE:
#         try:
#             enc = encoding_for_model(model)
#             return len(enc.encode(text))
#         except Exception:
#             # fallback to generic encoding
#             enc = tiktoken.get_encoding("utf-8")
#             return len(enc.encode(text))
#     # fallback heuristic: ~1 token per 4 characters (conservative)
#     return max(1, len(text) // 4)

def count_text_tokens_for_model(model, text):
    try:
        # Try the known tokenizer for this model
        enc = tiktoken.encoding_for_model(model)
    except KeyError:
        # Fallback tokenizer when model is unknown
        enc = tiktoken.get_encoding("cl100k_base")

    return len(enc.encode(text))

def estimate_total_input_tokens(model: str, prompt_text: str, images: List[Dict]) -> int:
    """Estimate combined token usage of prompt text plus images."""
    total = count_text_tokens_for_model(model, prompt_text)
    for img in images:
        total += estimate_image_tokens_from_bytes(img["bytes_len"])
    return total

# -------------------------
# Chunking images into batches
# -------------------------
def chunk_images_by_token_limit(model: str, prompt_text: str, images: List[Dict], max_tokens: int = MAX_INPUT_TOKENS) -> List[List[Dict]]:
    """
    Returns list of image batches where each batch when combined with prompt_text
    is estimated to be <= max_tokens (best-effort).
    """
    batches = []
    current_batch = []
    current_tokens = count_text_tokens_for_model(model, prompt_text)

    for img in images:
        img_tokens = estimate_image_tokens_from_bytes(img["bytes_len"])
        # If single image itself exceeds max_tokens, still place it in its own batch
        if current_tokens + img_tokens > max_tokens:
            if current_batch:
                batches.append(current_batch)
            # start new batch
            current_batch = [img]
            current_tokens = count_text_tokens_for_model(model, prompt_text) + img_tokens
            # If even this is > max, we still keep it: model must reject if too big
            if current_tokens > max_tokens:
                print(f"⚠️ single image '{img['filename']}' exceeds token limit by estimate ({current_tokens} tokens).")
                # append as its own batch and reset
                batches.append(current_batch)
                current_batch = []
                current_tokens = count_text_tokens_for_model(model, prompt_text)
        else:
            current_batch.append(img)
            current_tokens += img_tokens

    if current_batch:
        batches.append(current_batch)
    return batches

# -------------------------
# Utility: Build messages for one call
# -------------------------
def build_messages(prompt_text: str, previous_output: str, images_batch: List[Dict]) -> list:
    """
    Compose the message structure expected by the user code: system + user with a content list
    where images are appended as image_url entries.
    """
    # user content items: the textual prompt, the previous output (if any), then images
    content_items = [{"type": "text", "text": prompt_text}]
    if previous_output:
        # Keep previous output as text block; caller may choose to trim it beforehand
        content_items.append({"type": "text", "text": previous_output})

    # Add images (data URLs)
    for img in images_batch:
        content_items.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img['base64']}"}})

    messages = [
        {"role": "system", "content": "You are an expert in website information architecture and FreeMind XML."},
        {"role": "user", "content": content_items},
    ]
    return messages

# -------------------------
# Truncate helper for previous output (to limit context growth)
# -------------------------
def truncate_text_to_token_budget(model: str, text: str, token_budget: int) -> str:
    """
    Truncate `text` to roughly `token_budget` tokens using tiktoken if available,
    otherwise by chars approximation.
    """
    if not text:
        return ""
    if TIKTOKEN_AVAILABLE:
        try:
            enc = encoding_for_model(model)
            tokens = enc.encode(text)
            if len(tokens) <= token_budget:
                return text
            truncated_tokens = tokens[-token_budget:]  # keep the last token_budget tokens (context from recent output)
            return enc.decode(truncated_tokens)
        except Exception:
            pass
    # Fallback: approximate characters per token ~4, keep last (token_budget*4) chars
    approx_chars = token_budget * 4
    return text[-approx_chars:]

# -------------------------
# Multi-stage orchestrator
# -------------------------
async def multi_stage_mindmap_generation(client, model: str, prompt_text: str, images: List[Dict], output_file: str,
                                   max_input_tokens: int = MAX_INPUT_TOKENS, truncate_prev_to_tokens: int = 200000):
    """
    1) chunk images by token budget
    2) sequentially call OpenAI for each batch
    3) include previous_output in next call (truncated to limit growth)
    4) return final output (string) and save to output_file
    """
    batches = chunk_images_by_token_limit(model, prompt_text, images, max_input_tokens)
    print(f"🔀 Created {len(batches)} batch(es) for model={model}")

    previous_output = ""
    final_output = None

    for idx, batch in enumerate(batches, start=1):
        print(f"\n➡️ Calling API for batch {idx}/{len(batches)} (images: {[b['filename'] for b in batch]})")
        # If previous_output exists, truncate it to avoid explosive growth
        prev_for_call = truncate_text_to_token_budget(model, previous_output, truncate_prev_to_tokens) if previous_output else ""

        messages = build_messages(prompt_text, prev_for_call, batch)
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=0.0,
                messages=messages
            )
            msg_text = resp.choices[0].message.content.strip()
            print(f"✅ API call {idx} completed. Received {len(msg_text)} characters.")
            # Use the full response as previous_output for next stage (but will be truncated next loop)
            previous_output = msg_text
            final_output = msg_text
        except Exception as e:
            print(f"❌ API error on batch {idx}: {e}")
            raise

    # After all batches, try to extract <map> XML from final_output
    if not final_output:
        raise RuntimeError("No final output returned from API.")

    start = final_output.find("<map")
    if start == -1:
        # Save raw output for inspection
        with open(output_file + ".raw.txt", "w", encoding="utf-8") as fh:
            fh.write(final_output)
        raise ValueError("Final output does not contain <map> XML. Raw output saved.")

    mm_xml = final_output[start:]
    # strip trailing triple backticks if present
    if mm_xml.endswith("```"):
        mm_xml = mm_xml[:-3].strip()

    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as fh:
        fh.write(mm_xml)
    print(f"\n🧭 Final FreeMind mindmap saved to: {output_file}")

    return output_file, mm_xml

# -------------------------
# Example prompt builder for Home page (user can adapt)
# -------------------------
def build_mindmap_prompt(page_name: str, all_links: List[Dict]) -> str:
    """Return the textual prompt instructions used for the generation."""
    # Short, precise prompt helps reduce tokens
    prompt = textwrap.dedent(f"""
     You are an intelligent assistant specialized in generating professional website mind maps 
                in valid FreeMind (.mm) XML format.

                ### Objective
                Analyze the provided webpage screenshot, context, and extracted links to generate a clear and 
                hierarchical mind map representing the website's structure and navigation.

                ### Rules & Structure
                1. The root node must always be the page title: .
                - It must include the **Header**, **Footer** as subnodes.
                - All other pages (e.g., About, Services, Contact, Login, Signup, etc.) should appear 
                    as subnodes of the Home Page Header.
                - The **Header** and **Footer** should only exist once — under the Home Page.
                2- Using images in  makes nodes inside footer and headerand pagecontent 
                3- Only include page-specific sections, forms, buttons, and visible links and content.
                4. Every visible major section of the webpage should be represented as a main node.
                5. Each node must be enriched with relevant **links**, **buttons**, and **form fields** 
                based on the provided data and visible content.
                6. Only include links that exist in the provided list:
                {json.dumps(all_links, indent=2)}
                8. If the page has forms:
                - Represent each form as a node.
                - Add its form fields (e.g., text boxes, dropdowns, submit buttons) as subnodes.
                9. If the page has buttons:
                - Represent each button as a node.
                - Include the visible button text or purpose as its subnode.
                10. If the page has bulleted or numbered lists:
                - Represent each list as a node.
                - Include each list item as a subnode.
                11. Ensure logical grouping and a consistent hierarchy reflecting the webpage layout.
                12. Maintain clean hierarchy — for example:
                    - Home Page
                    - Header
                        - Navigation Links
                          - Sub links
                        - Main Content
                        - Visible Sections
                    - Footer
                13. Output must be valid XML conforming to FreeMind (.mm) syntax.
                14. **Do not** include any commentary, markdown formatting, or explanations in the output.

                ### Expected Output
                Return only a valid FreeMind (.mm) XML file structure representing the page hierarchy, 
                with proper nesting, link grouping, and visible UI elements.
                """).strip()
    return prompt

# -------------------------
# CLI-like main
# -------------------------
async def home_page(
    screenshots_folder,
    links_file,
    output_mm_file,
    compress_images: bool = False,
    model: str = DEFAULT_MODEL
):
    os.makedirs(screenshots_folder, exist_ok=True)
    client =await configure_openai_with_opik()  # tracked client
    # Load links
    if not os.path.exists(links_file):
        raise FileNotFoundError(f"{links_file} not found.")
    with open(links_file, "r", encoding="utf-8") as fh:
        links = json.load(fh)
    print("loading image")
    images =await load_images_as_base64(screenshots_folder, compress=compress_images)

    if not images:
        raise RuntimeError("No images found to process.")
    print("loading image")
    prompt = build_mindmap_prompt("Home", links)

    # quick estimation
    est_tokens = estimate_total_input_tokens(model, prompt, images)
    print(f"\n📊 Estimated total input tokens (prompt + images) = {est_tokens}")

    if est_tokens <= MAX_INPUT_TOKENS:
        # single call -- wrap images into one batch
        batches = [images]
    else:
        # automatically chunk by token budget
        batches = chunk_images_by_token_limit(model, prompt, images, MAX_INPUT_TOKENS)
        print(f"⚖️ Split into {len(batches)} batches to respect {MAX_INPUT_TOKENS} token limit.")

    # run the multi-stage orchestrator (it will call chunker internally too)
    out_file, mm_xml =await multi_stage_mindmap_generation(
        client=client,
        model=model,
        prompt_text=prompt,
        images=images,
        output_file=output_mm_file,
        max_input_tokens=MAX_INPUT_TOKENS,
        truncate_prev_to_tokens=200000  # keep previous output up to ~200k tokens (tunable)
    )
    replace_ampersand_with_space(out_file,out_file)
    print("🎯 Done.")

if __name__ == "__main__":
    screenshots_folder="dmaid/screenshot/home"
    links_file="dmaid/home_page_links.json"
    output_mm_file="dmaid/mindmaps/home.mm"

    asyncio.run(
        home_page(
            screenshots_folder,
            links_file,
            output_mm_file,
            compress_images=True,
            model=DEFAULT_MODEL
        )
    )