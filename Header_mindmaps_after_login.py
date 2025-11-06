import os
import json
import asyncio
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
# FUNCTION: GENERATE MINDMAP
# -------------------------------
def generate_mindmap_from_screenshot(image_path, page_name, all_links, mindmap_folder):
    """Generate a .mm mindmap file based on webpage screenshot and links."""
    # Convert image to bytes
    with open(image_path, "rb") as f:
        image_data = f.read()

    # 🧠 Smart Prompt for Gemini
    if page_name.lower() in ["home", "homepage"]:
        prompt = f"""
            You are an intelligent assistant specialized in generating professional website mind maps 
            in valid FreeMind (.mm) XML format.

            ### Objective
            Analyze the provided webpage screenshot, context, and extracted links to generate a clear and 
            hierarchical mind map representing the website's structure and navigation.

            ### Rules & Structure
            1. The root node must always be the page title: "{page_name}".
            2. If the page title is "Home" (or "Homepage"):
            - It must include the **Header**, **Footer** as subnodes.
            - All other pages (e.g., About, Services, Contact, Login, Signup, etc.) should appear 
                as subnodes of the Home Page Header.
            - The **Header** and **Footer** should only exist once — under the Home Page.
            3. For non-home pages:
            - The **Header** and **Footer** must **not** be repeated.
            - Only include page-specific sections, forms, buttons, and visible links and content.
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
            10. Ensure logical grouping and a consistent hierarchy reflecting the webpage layout.
            12. Maintain clean hierarchy — for example:
                - Home Page
                - Header
                    - Navigation Links
                    - Main Content
                    - Visible Sections
                - Footer
            13. Output must be valid XML conforming to FreeMind (.mm) syntax.
            14. **Do not** include any commentary, markdown formatting, or explanations in the output.

            ### Expected Output
            Return only a valid FreeMind (.mm) XML file structure representing the page hierarchy, 
            with proper nesting, link grouping, and visible UI elements.
            If the provided .mm file contains invalid XML special characters (like &, <, >, ", or '), replace them with their valid XML entity equivalents (&amp;, &lt;, &gt;, &quot;, &apos;) and return a well-formed FreeMind .mm XML file only
            """
    else:
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
                {json.dumps(all_links, indent=2)}
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
            """    
    try:
        response = client.chat.completions.create(
            model="gpt-4.1",
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
            temperature=0.3,
        )
        mindmap_content = response.choices[0].message.content.strip()
        start_index = mindmap_content.find("<map")
        if start_index == -1:
            raise ValueError("OpenAI output does not contain valid <map> XML structure.")

        mindmap_content = mindmap_content[start_index:].strip()
        # 🧹 Remove closing ``` if present
        if mindmap_content.endswith("```"):
            mindmap_content = mindmap_content[:-3].strip()
        lines= mindmap_content.splitlines()
        # Ensure valid .mm extension file is saved
        cleaned_mindmap = "\n".join(lines).strip()
        output_path = os.path.join(mindmap_folder, f"{page_name}.mm")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(cleaned_mindmap)

        print(f"🧭 Mindmap generated → {output_path}")
        return output_path
    except Exception as e:
        print(f"❌ Error generating mindmap for {page_name}: {e}")
        return None


# -------------------------------
# MAIN WORKFLOW
# -------------------------------
async def header(base_folder="."):
    HEADERS_FOLDER = os.path.join(base_folder, "headers_After_Login")
    SCREENSHOT_FOLDER = os.path.join(base_folder, "screenshots_After_Login")
    MINDMAP_FOLDER = os.path.join(base_folder, "mindmaps_After_Login")
    os.makedirs(MINDMAP_FOLDER, exist_ok=True)

    print("🚀 Starting Mindmap Generation from Existing Data")

    if not os.path.exists(HEADERS_FOLDER):
        print(f"❌ Folder '{HEADERS_FOLDER}' not found.")
        return

    if not os.path.exists(SCREENSHOT_FOLDER):
        print(f"❌ Folder '{SCREENSHOT_FOLDER}' not found.")
        return

    # Loop through all JSON files in headers/
    for header_file in sorted(os.listdir(HEADERS_FOLDER)):
        if not header_file.endswith(".json"):
            continue

        page_name = os.path.splitext(header_file)[0]
        header_path = os.path.join(HEADERS_FOLDER, header_file)
        screenshot_path = os.path.join(SCREENSHOT_FOLDER, f"{page_name}.png")

        if not os.path.exists(screenshot_path):
            print(f"⚠️ No screenshot found for {page_name}, skipping.")
            continue

        with open(header_path, "r", encoding="utf-8") as f:
            all_links = json.load(f)

        print(f"\n📄 Processing: {page_name}")
        print(f"🔗 Found {len(all_links)} links in {header_file}")
        print(f"📸 Screenshot path: {screenshot_path}")

        generate_mindmap_from_screenshot(screenshot_path, page_name, all_links, MINDMAP_FOLDER)

    print(f"\n✅ All mindmaps generated successfully in '{MINDMAP_FOLDER}' folder!")

# # -------------------------------
# # ENTRY POINT
# # -------------------------------
# if __name__ == "__main__":
#     asyncio.run(header())
