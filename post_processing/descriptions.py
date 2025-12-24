
import os
import re
from lxml import etree as ET  # <-- use lxml instead of xml.etree.ElementTree

# ========================
# Common button descriptions
# ========================
BUTTON_DESCRIPTIONS = {
    "home": "Navigates to the main landing page or dashboard.",
    "about": "Displays information about the organization or product.",
    "contact": "Opens contact form or company contact details.",
    "help": "Leads to FAQs, support tickets, or live chat.",
    "dashboard": "Centralized area showing user stats and quick actions.",
    "profile": "User profile details and account settings.",
    "logout": "Ends user session and logs out of the system.",
    "settings": "Allows customization of account, preferences, or system options.",
    "notifications": "Shows recent alerts or updates.",
    "language": "Lets users change website language or location preferences.",
    "login": "Opens authentication form to access user account.",
    "sign in": "Opens authentication form to access user account.",
    "register": "Allows new users to create an account.",
    "sign up": "Allows new users to create an account.",
    "forgot password": "Redirects to password recovery flow.",
    "reset password": "Lets user reset credentials via email or code.",
    "verify email": "Confirms user’s email after signup.",
    "continue as guest": "Lets user browse without logging in.",
    "submit": "Sends form data to the server.",
    "save": "Stores entered information without submitting.",
    "cancel": "Discards current input or closes the form.",
    "next": "Moves to the next step in a process or wizard.",
    "back": "Returns to the previous screen or step.",
    "upload": "Allows file or image upload.",
    "download": "Triggers file or report download.",
    "edit": "Opens item for modification.",
    "delete": "Permanently deletes selected record.",
    "add": "Creates a new entry or record.",
    "add new": "Creates a new entry or record.",
    "add member": "Adds a new team member.",
    "add to cart": "Adds selected product to shopping cart.",
    "checkout": "Proceeds to payment and order confirmation.",
    "subscribe": "Starts a subscription or membership plan.",
    "renew membership": "Extends current membership period.",
    "view order history": "Displays list of past purchases.",
    "manage users": "Opens user list and permission controls.",
    "view reports": "Displays analytics or performance reports.",
    "approve": "Accepts pending requests.",
    "reject": "Denies pending requests.",
    "export data": "Downloads dataset in Excel/CSV/PDF format.",
    "import data": "Uploads bulk records from file.",
    "generate report": "Creates a summarized document based on filters.",
    "assign role": "Updates user access levels.",
    "message": "Opens a direct message or chat box.",
    "comment": "Adds a note or feedback to an item.",
    "reply": "Responds to an existing comment or thread.",
    "share": "Shares content via link or social media.",
    "invite": "Sends an invitation to new team members.",
    "search": "Executes a search query across site data.",
    "filter": "Narrows down data using specific criteria.",
    "refresh": "Reloads the current page or data.",
    "view details": "Opens detailed information of selected item.",
    "print": "Sends current page or data to printer.",
    "expand": "Expands the section for more details.",
    "collapse": "Collapses the section to hide details.",
    "footer": "Displays footer information and links.",
    "Submit": "Thanks for submitting the form! We will get back to you shortly.",
    "Subscribe": "Thank you for subscribing to our newsletter! Stay tuned for updates.",
    "Request a Demo Button": "Requests a personalized demonstration of our services.",
    "Request a Demo ": "Requests a personalized demonstration of our services.",    
    "demo ": "Requests a personalized demonstration of our services."
}

# ========================
# Helper Functions
# ========================
def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    text = text.lower().strip()
    text = re.sub(r"[_\-]+", " ", text)
    return text


# def collapse_all_nodes(root):
#     """Ensure all nodes are collapsed (FOLDED=true)."""
#     for node in root.iter("node"):
#         node.set("FOLDED", "true")

def collapse_all_nodes(input_file, output_file=None):
    """Collapse all <node> elements by setting FOLDED='true'."""
    if output_file is None:
        output_file = input_file  # overwrite input if no output specified

    print(f"🔍 Reading mindmap: {input_file}")
    parser = ET.XMLParser(remove_blank_text=False)
    tree = ET.parse(input_file, parser)
    root = tree.getroot()

    count = 0
    for node in root.iter("node"):
        node.set("FOLDED", "true")
        count += 1

    # Write back, preserving <richcontent> sections
    tree.write(
        output_file,
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=True,
    )

    print(f"✅ Collapsed {count} nodes in: {output_file}")



def add_description_nodes(root):
    """Add descriptions to matching nodes."""
    updated_count = 0
    added_descriptions = set()

    for node in root.iter("node"):
        # Skip screenshot nodes (so we don’t corrupt <richcontent>)
        if node.find("richcontent") is not None:
            continue

        text = node.attrib.get("TEXT", "")
        normalized = normalize_text(text)

        for key, desc in BUTTON_DESCRIPTIONS.items():
            if re.search(rf"\b{re.escape(key)}\b", normalized):
                already_has = any(
                    desc in (child.attrib.get("TEXT", "") or "")
                    for child in node.findall("node")
                )
                if not already_has:
                    desc_node = ET.Element("node", TEXT=desc)
                    desc_node.set("FOLDED", "true")
                    node.append(desc_node)
                    added_descriptions.add(desc)
                    updated_count += 1
                    print(f"✅ Added description for: {text}")
                break
    return updated_count


def process_mindmap(input_file, output_file):
    """Main processing function."""
    print(f"🔍 Reading mindmap: {input_file}")

    # Use parser that preserves formatting and HTML content
    parser = ET.XMLParser(remove_blank_text=False)
    tree = ET.parse(input_file, parser)
    root = tree.getroot()

    # Step 1: Collapse all nodes

    # Step 2: Add descriptions
    updated = add_description_nodes(root)

    # collapse_all_nodes(input_file, output_file)
    count = 0
    for node in root.iter("node"):
        node.set("FOLDED", "true")
        count += 1
    # Step 3: Save final file (screenshots preserved!)
    tree.write(
        output_file,
        encoding="utf-8",
        xml_declaration=True,
        pretty_print=True,
    )

    print(f"\n💾 Saved updated mindmap: {output_file}")
    print(f"🧠 Total nodes updated with descriptions: {updated}")


# ========================
# Runner
# ========================
# if __name__ == "__main__":
#     INPUT_MM = r"comp360software\Full_Website_Structure_with_screenshots.mm"
#     OUTPUT_MM = r"comp360software\Full_Website_Structure_updated_with_descriptions.mm"

#     if not os.path.exists(INPUT_MM):
#         print("❌ Input file not found.")
#     else:
#         process_mindmap(INPUT_MM, OUTPUT_MM)
