import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from opik import configure
import xml.etree.ElementTree as ET
from opik.integrations.openai import track_openai

def add_attributes_to_nodes(input_path, output_path):
    """
    Add FOLDED='true' and POSITION='left' to every <node> element in a .mm file.
    Keeps existing attributes unchanged.
    """

    tree = ET.parse(input_path)
    root = tree.getroot()

    for node in root.iter("node"):
        # Add only if missing
        if "FOLDED" not in node.attrib:
            node.set("FOLDED", "true")
        if "POSITION" not in node.attrib:
            node.set("POSITION", "left")

    # Save updated XML
    tree.write(output_path, encoding="utf-8", xml_declaration=False)

def configure_openai():
    """Configure OpenAI GPT client with Opik tracing."""
    load_dotenv()
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        raise ValueError("❌ OPENAI_API_KEY not found in .env file.")

    configure()
    client = OpenAI(api_key=OPENAI_API_KEY)
    return track_openai(client)


def load_mindmap(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def generate_testcases(client, mindmap_structure: str,header_links) -> str:
    with open(header_links, 'r', encoding='utf-8') as f:
        data = json.load(f)
    header_names = [item["text"] for item in data]
    header_names.append("Home Page")
    """Generate test cases using GPT."""
    testcase_prompt = f"""
    You are generating detailed UI and functional test cases for a website.  
    Your job is to produce a complete, strictly formatted FreeMind (.mm) XML mindmap.

    ===========================================================
    INPUT DATA
    ===========================================================

    WEBSITE MINDMAP STRUCTURE:
    {mindmap_structure}

    HEADER LINKS (JSON SOURCE OF TRUTH):
    {header_names}

    IMPORTANT:
    The JSON list of header links is the ONLY source of truth.
    IGNORE the original mindmap if it contains different or missing links.
    Every link from the JSON MUST appear in the output.
    No link may be skipped, merged, grouped, or renamed.

    ===========================================================
    MANDATORY TEST CASE RULES
    ===========================================================

    For EACH header link in the JSON list (no exceptions):

    You MUST generate exactly:
    • 10 Positive Functional test cases  
    • 10 Negative Functional test cases  
    • 10 Non-Functional test cases  

    Total per link = 30 test cases  
    Total overall = 30 × (number of links)

    Test cases MUST be:
    • Clear, complete sentences  
    • Realistic, UI/UX and end-to-end behavior based  
    • Written inside <node TEXT="..."/> elements  
    • All '&' replaced with '&amp;' inside TEXT attributes  

    ===========================================================
    STRICT XML OUTPUT RULES
    ===========================================================

    You MUST output a valid FreeMind mindmap with this exact structure:

    1. Output MUST contain exactly ONE <map version="1.0.1"> root.
    2. Output MUST contain exactly ONE top-level <node TEXT="Test Cases">.
    3. For every header link in the JSON list, create:

    <node TEXT="[Link Text] Test Cases" POSITION="left" FOLDED="true">
        <node TEXT="Positive Functional" POSITION="left" FOLDED="true">
            <node TEXT="1. ..."/>
            <node TEXT="2. ..."/>
            ...
            <node TEXT="10. ..."/>
        </node>

        <node TEXT="Negative Functional" POSITION="left" FOLDED="true">
            <node TEXT="1. ..."/>
            ...
            <node TEXT="10. ..."/>
        </node>

        <node TEXT="Non-Functional" POSITION="left" FOLDED="true">
            <node TEXT="1. ..."/>
            ...
            <node TEXT="10. ..."/>
        </node>
    </node>

    4. Every <node> MUST contain:
    • POSITION="left"
    • FOLDED="true"  
    (Except inner test-case items, which have only TEXT)

    5. No XML declaration (NO "<?xml…?>").
    6. Absolutely NO comments, NO markdown, NO explanation text.
    7. Only <map> and <node> elements may appear.

    ===========================================================
    REQUIRED OUTPUT TEMPLATE
    ===========================================================

    <map version="1.0.1">
    <node TEXT="Test Cases" POSITION="left" FOLDED="true">

        <!-- REPEAT THIS BLOCK FOR EVERY HEADER LINK -->
        <node TEXT="[Header Link Text] Test Cases" POSITION="left" FOLDED="true">
        <node TEXT="Positive Functional" POSITION="left" FOLDED="true">
            <node TEXT="1. ..."/>
            ...
        </node>
        <node TEXT="Negative Functional" POSITION="left" FOLDED="true">
            ...
        </node>
        <node TEXT="Non-Functional" POSITION="left" FOLDED="true">
            ...
        </node>
        </node>

    </node>
    </map>

    ===========================================================
    NOW GENERATE THE FINAL .MM OUTPUT
    ===========================================================

    Generate the final output using EXACTLY the structure and rules above.
    """


    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": testcase_prompt}],
        temperature=0.0,
    )

    return response.choices[0].message.content


def save_raw_output(content: str, output_path: str):
    """Save GPT output directly, no wrapping."""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)


def filter_mm(input_path, output_path):
    with open(input_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    count_end_map = sum(line.strip() == "</map>" for line in lines)
    count_open_map = sum("<map version='1.0.1'>" in line for line in lines)
    print(f"Found {count_open_map} opening <map> tags and {count_end_map} closing </map> tags.")
    # Rule 1
    if count_end_map > 1:
        lines = lines[:-2]

    # Rule 2
    if count_open_map > 1:
        lines = lines[2:]

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def testcases(mindmap_path, raw_output_path, final_output_path,header_links):
    # mindmap_path = "dayzee/Full_Website_Structure_updated.mm"
    # raw_output_path = "dayzee/raw_model_output.mm"
    # final_output_path = "dayzee/Generated_TestCases.mm"

    print("Loading mindmap...")
    mindmap_structure = load_mindmap(mindmap_path)

    print("Configuring OpenAI client...")
    client = configure_openai()

    print("Generating test cases...")
    testcases_content = generate_testcases(client, mindmap_structure,header_links)

    print("Saving raw GPT output...")
    save_raw_output(testcases_content, raw_output_path)

    print("Filtering duplicate map tags...")
    filter_mm(raw_output_path, final_output_path)
    add_attributes_to_nodes(final_output_path, final_output_path)
    print(f"✅ Final filtered mindmap generated: {final_output_path}")


if __name__ == "__main__":
    mindmap_path = r"comp360software/Full_Website_Structure_updated.mm"
    raw_output_path = r"comp360software/raw_model_output.mm"
    final_output_path = r"comp360software/Generated_TestCases.mm"
    header_links= r"comp360software/header_links.json"

    testcases(mindmap_path,final_output_path,final_output_path,header_links)
