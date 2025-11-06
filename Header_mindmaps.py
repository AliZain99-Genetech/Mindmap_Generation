import os
import json
import asyncio
from playwright.async_api import async_playwright # pyright: ignore[reportMissingImports]
from openai import OpenAI # type: ignore
from dotenv import load_dotenv # type: ignore

# -------------------------------
# CONFIGURATION
# -------------------------------
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("❌ OPENAI_API_KEY not found in .env file")
client = OpenAI(api_key=api_key)


# -------------------------------
# FUNCTION: TAKE SCREENSHOT
# -------------------------------
async def take_screenshot(url, name, screenshot_folder):
    """Takes a full-page screenshot and saves it in /screenshots"""
    print(f"📸 Taking screenshot of {url}...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=120000)
            await page.wait_for_timeout(5000)
            screenshot_path = os.path.join(screenshot_folder, f"{name}.png")
            await page.screenshot(path=screenshot_path, full_page=True)
            print(f"📸 Screenshot saved: {screenshot_path}")
            return screenshot_path
        except Exception as e:
            print(f"❌ Failed to load {url}: {e}")
            return None
        finally:
            await browser.close()


# -------------------------------
# FUNCTION: GENERATE MINDMAP USING GEMINI
# -------------------------------
def generate_mindmap_from_screenshot(image_path, page_name, all_links,output_folder):
    """Generate a .mm mindmap file based on webpage screenshot and links."""
    # Convert image to bytes
    with open(image_path, "rb") as f:
        image_data = f.read()

    # 🧠 Smart Prompt for Gemini
    if page_name.lower() in ["home", "homepage"]:
        prompt = f"""
    You are **MindArchitect-GPT**, an intelligent assistant trained in information architecture, UX design, and FreeMind XML structure generation.

    ---

    ### 🧠 BACKSTORY
    You are part of an AI research team that automatically reverse-engineers website navigation flows into hierarchical mind maps.  
    Your goal is to produce **well-structured, accurate, and valid `.mm` XML** documents compatible with FreeMind or Freeplane software.  
    You have been provided a webpage **screenshot** and its **header-level links** for context.

    ---

    ### 🎯 PURPOSE
    Generate a professional, complete `.mm` mindmap that represents the **website’s structure, hierarchy, and navigation**.

    ---

    ### 🧩 POMAL FRAMEWORK

    **P (Purpose):** Convert webpage screenshot and extracted link data into a FreeMind (.mm) XML hierarchy.  
    **O (Objective):** Show the logical layout of the website — header, footer, main content, sections, and navigation links.  
    **M (Method):**
    1. Parse the provided screenshot visually (mentally simulate it).
    2. Use the given links JSON to identify main and sub-pages.
    3. Organize all visible and structural elements into clean XML nodes.
    4. If a section is text-only → summarize its visible text in one short descriptive line.
    5. If a section includes forms, buttons, or links → represent those as nested nodes. 
    **A (Action):**
    - Output strictly valid XML conforming to FreeMind format.  
   - Each node should have meaningful `TEXT` attributes and `LINK` if available.  
   - Use single-line summaries for long paragraphs
    **L (Limitation):**
    - Do **not** output markdown, commentary, or plain text explanations.    
    - Do **not** duplicate header or footer nodes.
    ---

    ### 🧱 RULES & STRUCTURE (for HOME PAGE)
    1. Root node must be the page title: "{page_name}".
    2. Must include **Header** and **Footer** as top-level subnodes.
    3. All other pages (e.g., About, Services, Contact, etc.) appear as subnodes under the Header.
    4. **Header** and **Footer** should appear only once — under Home Page.
    5. Every visible section or navigation item should be a nested `<node>` element.
    6. Add LINK attributes to mindmap nodes to make them clickable hyperlinks (e.g., <node TEXT='Google' LINK='https://www.google.com'/>)
    7. Maintain consistent hierarchy depth — Header → Navigation → Section → Element.
    8. Output only XML (no markdown, bullets, or extra explanations).

    ---

    ### 🧩 INPUT LINKS (Context)
    {json.dumps(all_links, indent=2)}

    ---

    ### 💡 FEW-SHOT EXAMPLE

    ### 💡 FEW-SHOT EXAMPLES

**Example 1 — Text-Only Section**

**Input Context:**
Screenshot shows a section with heading "About Us" and 3 short paragraphs about the company mission.
No buttons or forms visible.

php-template


**Expected Output:**

<map version="1.0.1">
  <node TEXT="About Page">
    <node TEXT="Main Content">
      <node TEXT="About Us">
        <node TEXT="We are a tech-driven company focused on building sustainable digital solutions."/>
      </node>
    </node>
  </node>
</map>
Example 2 — Section With Buttons

Input Context:



Section title: "Join Our Team"
Visible button: "Apply Now"
Link: https://example.com/careers
Expected Output:

xml

<map version="1.0.1">
  <node TEXT="Careers Page">
    <node TEXT="Main Content">
      <node TEXT="Join Our Team">
        <node TEXT="Apply Now" LINK="https://example.com/careers"/>
      </node>
    </node>
  </node>
</map>
Example 3 — Form Section

Input Context:

makefile

Section: Contact Us
Fields: Name, Email, Message
Button: Send Message
Link: https://example.com/contact
Expected Output:


<map version="1.0.1">
  <node TEXT="Contact Page">
    <node TEXT="Main Content">
      <node TEXT="Contact Form">
        <node TEXT="Name Field"/>
        <node TEXT="Email Field"/>
        <node TEXT="Message Field"/>
        <node TEXT="Send Message" LINK="https://example.com/contact"/>
      </node>
    </node>
  </node>
</map>

    **Expected Output (Shortened):**
    <map version="1.0.1">
    <node TEXT="Home">
        <node TEXT="Header">
        <node TEXT="Navigation Links">
            <node TEXT="About" LINK="https://example.com/about"/>
            <node TEXT="Contact" LINK="https://example.com/contact"/>
        </node>
        </node>
        <node TEXT="Footer"/>
    </node>
    </map>
    Now, using the provided screenshot and link context, generate the full .mm XML for the Home Page only.
    Ensure it validates as proper XML with escaped entities and clear hierarchy.
    🪄 OUTPUT REQUIREMENTS

        Output only valid XML — no markdown or prose.

        Maintain indentation, hierarchy, and clean one-line summaries for text-only sections.

        Output must be directly usable as a .mm file.

        Now, using the provided screenshot and link context, generate the .mm XML mindmap for the page titled {page_name}.
    """
    else:
        prompt = f"""
        You are MindArchitect-GPT, an advanced assistant that converts webpage screenshots and link data into clean FreeMind (.mm) XML mind maps.

        🧠 BACKSTORY
        You specialize in analyzing visual webpage structures and producing valid, concise XML hierarchies representing content flow, forms, and UI elements.

        🎯 PURPOSE
        Produce a .mm file that represents only the page-specific visible content, excluding the header and footer.

        🧩 POMAL FRAMEWORK
        **P (Purpose):** Create a hierarchical mindmap of the webpage structure.  
    **O (Objective):** Capture meaningful sections, forms, buttons, and links based on the screenshot and link data.  
    **M (Method):**
    1. Visually interpret the screenshot layout.  
    2. Group content into clear sections (e.g., “Hero Section,” “About,” “Contact,” etc.).  
    3. If a section is text-only → summarize its visible text in one short descriptive line.  
    4. If a section includes forms, buttons, or links → represent those as nested nodes.  
    5. Use provided link data for hyperlink nodes.  
    **A (Action):**
    - Output strictly valid XML conforming to FreeMind format.  
    - Each node should have meaningful `TEXT` attributes and `LINK` if available.  
    - Use single-line summaries for long paragraphs.  
    **L (Limitations):**
    - Do **not** output markdown, commentary, or plain text explanations.  
    - Properly escape XML entities (`& → &amp;`, `< → &lt;`, `>` → &gt;`).  
    - Do **not** duplicate header or footer nodes.
    
        🧭 STRUCTURE RULES (for non-Home pages)
        1. Root node: "{page_name}"  
    2. Skip all Header and Footer elements.  
    3. Organize main content hierarchically:
    - Page Title  
        - Main Content  
            - Visible Section 1  
            - Visible Section 2  
            - Forms  
            - Buttons  
    4. For **forms**:
    - Represent each input field as a child node.  
    - Include buttons with their visible text.  
    5. For **buttons**:
    - Use visible button text or purpose (e.g., "Submit Form", "Learn More").  
    6. For **text-only sections**:
    - Create a node named after its visible heading or logical title.
    - Inside, add one summary node that captures the text meaning in one line (no full paragraphs).
    7 For **links**:
    - Use `LINK` attributes for clickable URLs. 

    ### 🧩 PROVIDED LINKS
        Use only these links when adding `LINK` attributes:
        {json.dumps(all_links, indent=2)}

        💡 FEW-SHOT EXAMPLE
        **Example 1 — Text-Only Section**

**Input Context:**
Screenshot shows a section with heading "About Us" and 3 short paragraphs about the company mission.
No buttons or forms visible.



**Expected Output:**

<map version="1.0.1">
  <node TEXT="About Page">
    <node TEXT="Main Content">
      <node TEXT="About Us">
        <node TEXT="We are a tech-driven company focused on building sustainable digital solutions."/>
      </node>
    </node>
  </node>
</map>
Example 2 — Section With Buttons

Input Context:


Section title: "Join Our Team"
Visible button: "Apply Now"
Link: https://example.com/careers
Expected Output:


<map version="1.0.1">
  <node TEXT="Careers Page">
    <node TEXT="Main Content">
      <node TEXT="Join Our Team">
        <node TEXT="Apply Now" LINK="https://example.com/careers"/>
      </node>
    </node>
  </node>
</map>
Example 3 — Form Section

Input Context:



Section: Contact Us
Fields: Name, Email, Message
Button: Send Message
Link: https://example.com/contact
Expected Output:

xml

<map version="1.0.1">
  <node TEXT="Contact Page">
    <node TEXT="Main Content">
      <node TEXT="Contact Form">
        <node TEXT="Name Field"/>
        <node TEXT="Email Field"/>
        <node TEXT="Message Field"/>
        <node TEXT="Send Message" LINK="https://example.com/contact"/>
      </node>
    </node>
  </node>
</map>
    
🪄 OUTPUT REQUIREMENTS

Output only valid XML — no markdown or prose.

Maintain indentation, hierarchy, and clean one-line summaries for text-only sections.

Output must be directly usable as a .mm file.

Now, using the provided screenshot and link context, generate the .mm XML mindmap for the page titled {page_name}.
        """
        
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_data.decode('utf-8')}"
                            },
                        },
                    ],
                }
            ],
            temperature=0.0,
        )
        mindmap_content = response.choices[0].message.content.strip()
        lines= mindmap_content.splitlines()
        if len(lines) > 2:
            lines = lines[1:-1]
        # Ensure valid .mm extension file is saved
        cleaned_mindmap = "\n".join(lines).strip()
        output_path = os.path.join(output_folder, f"{page_name}.mm")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(cleaned_mindmap)

        print(f"🧭 Mindmap generated → {output_path}")
        return output_path

    except Exception as e:
        print(f"❌ Error generating mindmap for {page_name}: {e}")
        return None


# -------------------------------
# MAIN FUNCTION (FOR INTEGRATION)
# -------------------------------
async def generate_mindmaps_from_headers(
    base_folder=".",  # 👈 new argument to represent the domain folder (e.g., "example.com")
    headers_folder=None,
    extracted_headers_path=None,
    output_folder=None,
    screenshot_folder=None
):
    """
    Main pipeline:
    1. Reads all header JSONs.
    2. Takes screenshots.
    3. Calls OpenAI to create .mm mindmaps.
    """


    # --- Resolve all folder paths relative to base_folder ---
    if headers_folder is None:
        headers_folder = os.path.join(base_folder, "headers")
    if extracted_headers_path is None:
        extracted_headers_path = os.path.join(base_folder, "header_links.json")
    if output_folder is None:
        output_folder = os.path.join(base_folder, "mindmaps")
    if screenshot_folder is None:
        screenshot_folder = os.path.join(base_folder, "screenshots")

    # --- Ensure output directories exist ---
    os.makedirs(output_folder, exist_ok=True)
    os.makedirs(screenshot_folder, exist_ok=True)

    # --- Input validation ---
    print(f"Checking for headers folder at: {headers_folder}")
    if not os.path.exists(headers_folder):
        print(f"❌ Folder '{headers_folder}' not found.")
        return

    if not os.path.exists(extracted_headers_path):
        print(f"❌ File '{extracted_headers_path}' not found.")
        return

    # --- Load extracted header links ---
    with open(extracted_headers_path, "r", encoding="utf-8") as f:
        header_data = json.load(f)

    header_url_map = {
        item["text"].strip().lower(): item["href"]
        for item in header_data if "href" in item
    }

    all_outputs = []

    # --- Process each header JSON file ---
    for header_file in sorted(os.listdir(headers_folder)):
        if not header_file.endswith(".json"):
            continue

        page_name = os.path.splitext(header_file)[0]
        header_path = os.path.join(headers_folder, header_file)

        try:
            with open(header_path, "r", encoding="utf-8") as f:
                all_links = json.load(f)
        except Exception as e:
            print(f"⚠️ Failed to load {header_file}: {e}")
            continue

        if not all_links:
            print(f"⚠️ No links found in {header_file}. Skipping...")
            continue

        page_url = header_url_map.get(page_name.lower())
        print(f"🔍 Mapped page name '{page_name}' to URL: {page_url}")
        if not page_url:
            print(f"⚠️ No matching URL found for '{page_name}' in header_links.json. Skipping...")
            continue

        print(f"\n🌐 Processing: {page_name.upper()} ({page_url})")

        # --- Take screenshot ---
        screenshot_path = await take_screenshot(page_url, page_name, screenshot_folder)
        if not screenshot_path:
            print(f"⚠️ Screenshot failed for {page_name}")
            continue

        # --- Generate mindmap using OpenAI ---
        output_path = generate_mindmap_from_screenshot(
            screenshot_path, page_name, all_links, output_folder
        )

        if output_path:
            all_outputs.append(output_path)

    print(f"\n✅ All mindmaps generated successfully in: {output_folder}")
    return all_outputs



# -------------------------------
# Allow running standalone
# -------------------------------
# if __name__ == "__main__":
#     asyncio.run(generate_mindmaps_from_headers())
