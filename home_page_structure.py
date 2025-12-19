import os
from dotenv import load_dotenv
from openai import OpenAI

def extract_structure_from_html(html_content: str) -> str:
    """Send HTML to OpenAI and return extracted structure."""
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    prompt = f"""
You are an expert in HTML semantic analysis and website architecture extraction.

Your task:
Analyze the provided HTML and output a **complete hierarchical structure** of the entire webpage.

Output Format Requirements (IMPORTANT):
- Use **tree-style ASCII formatting** exactly like this:
  SECTION
  ├── Subsection
  │   ├── Item 1
  │   └── Item 2
  └── Another Subsection
- Use these characters exactly:
  • ├──
  • └──
  • │
- The very top node should be the **website name or page title**.
- Output MUST be **plain text**, no markdown, no code blocks.

Content Requirements:
- Include ALL sections:
  • Header
  • Navigation menu
  • Dropdowns + nested dropdowns (VERY important)
  • Hero banner
  • All content sections
  • Sliders, cards, icons, forms
  • Footer with all nested lists
  • Modals, popups, sticky buttons, floating widgets
  • Any hidden menus or expandable items
- Identify each block by its role or visible text.
- Use indentation to accurately show hierarchy.
- Summaries should use semantic labels + key text (e.g., "Our Services", "AI Solutions").
- DO NOT include:
  • scripts
  • analytics
  • meta tags
  • styling
  • inline JS
  • boilerplate HTML

Your output must follow this exact style example:

GENETECH SOLUTIONS WEBSITE
├── HEADER
│   ├── Logo & Branding
│   ├── Navigation Menu
│   │   ├── Services 
│   │   │   ├── IT Staff Augmentation
│   │   │   ├── Software Engineering
│   │   │   │   ├── Product Engineering
│   │   │   │   ├── AI-Powered Business Solutions
│   │   │   │   └── QA Automation
│   │   ├── Industries
│   │   └── Contact
├── HERO SECTION
│   ├── Main Heading
│   └── CTA Button
└── FOOTER
    ├── Quick Links
    └── Social Links

Now generate the FULL structure for the HTML below:

HTML INPUT:
----------------
{html_content}
----------------
"""

    response = client.chat.completions.create(
        model="gpt-5.1",
        messages=[
            {"role": "system", "content": "You extract page structure from HTML."},
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content


def html_file_to_structure(input_html_path: str, output_txt_path: str):
    """Read HTML file, extract structure, save to .txt file."""
    # Load environment variables
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY not found in .env file")

    # Read HTML file
    with open(input_html_path, "r", encoding="utf-8") as f:
        html_data = f.read()

    # Extract structure using OpenAI
    structure = extract_structure_from_html(html_data)

    # Save result to txt
    with open(output_txt_path, "w", encoding="utf-8") as f:
        f.write(structure)

    print(f"✅ Page structure saved to {output_txt_path}")


if __name__ == "__main__":
    input_html = r"genetechz\HTML\page_source.html"    # your HTML file
    output_txt = r"genetechz\Structure\home_structure.txt"  # output file

    html_file_to_structure(input_html, output_txt)
