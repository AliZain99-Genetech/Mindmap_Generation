import os
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
import copy
import re

def normalize(text: str) -> str:
    """
    Normalize for best matching:
    - lowercase
    - remove non-alphanumeric chars like @ - _
    - collapse multiple spaces
    """
    text = text.lower().strip().strip()

    # Replace any non letter/digit with space
    text = re.sub(r"[^a-z0-9]+", " ", text)

    # collapse multiple spaces
    text = " ".join(text.split())

    return text

def find_matching_header(normalized_page, header_node):
    candidates = []

    # Normalize words
    page_words = set(re.findall(r"\w+", normalized_page))

    # --------------------------------------------------------
    # 🔥 NEW: Search only level-1 and level-2 children of Header
    # --------------------------------------------------------
    level1 = header_node.findall("./node")          # direct children under Header
    level2 = header_node.findall(".//node/node")
    level3 = header_node.findall(".//node/node/node")  # one level deeper
    search_nodes = level1 + level2 + level3                  # combine both levels
    # --------------------------------------------------------

    for node in search_nodes:
        node_text = node.attrib.get("TEXT", "")
        normalized_header = normalize(node_text)
        header_words = set(re.findall(r"\w+", normalized_header))

        # 1. Exact match (highest priority)
        if normalized_page == normalized_header:
            return node

        # 2. Singular/plural match (score 5)
        if re.fullmatch(rf"{re.escape(normalized_header)}s?", normalized_page) or \
           re.fullmatch(rf"{re.escape(normalized_page)}s?", normalized_header):
            candidates.append((node, 5))

        # 3. All words contained (score 4)
        if page_words.issubset(header_words) or header_words.issubset(page_words):
            candidates.append((node, 4))

        # 4. Starts-with match (score 3)
        if normalized_header.startswith(normalized_page) or normalized_page.startswith(normalized_header):
            candidates.append((node, 3))

        # 5. Word-by-word contains match (score 2)
        if re.search(rf"\b{re.escape(normalized_page)}\b", normalized_header) or \
           re.search(rf"\b{re.escape(normalized_header)}\b", normalized_page):
            candidates.append((node, 2))

        # 6. Substring match (score 1)
        if normalized_page in normalized_header or normalized_header in normalized_page:
            candidates.append((node, 1))

    if not candidates:
        return None

    # Return highest-scoring match
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates[0][0]
def convert_links_in_mm(input_mm_path, output_mm_path):
    tree = ET.parse(input_mm_path)
    root = tree.getroot()

    for node in root.iter("node"):
        text = node.get("TEXT")
        if text and (text.startswith("http://") or text.startswith("https://")):
            # Parse URL
            parsed = urlparse(text)
            path = parsed.path.rstrip("/")

            # Get last part of URL
            last_part = path.split("/")[-1] if path else parsed.netloc

            # Update node attributes
            node.set("TEXT", last_part)
            node.set("LINK", text)

    tree.write(output_mm_path, encoding="utf-8", xml_declaration=True)
def merge_mindmaps(base_folder):
    """
    Merge all .mm mindmaps for a given domain into a single master mindmap.

    Creates or updates: base_folder/Merged_Website_Structure.mm
    """

    mindmap_folder = os.path.join(base_folder, "mindmaps")
    master_path = os.path.join(mindmap_folder, "home.mm")
    output_path = os.path.join(base_folder, "Merged_Website_Structure.mm")

    # --- Validate mindmap folder ---
    if not os.path.exists(mindmap_folder):
        raise FileNotFoundError(f"❌ Mindmap folder not found: {mindmap_folder}")

    # --- Create master mindmap if missing ---
    if not os.path.exists(master_path):
        print(f"⚠️ Master mindmap not found. Creating a new one at: {master_path}")

        root = ET.Element("map", version="freeplane 1.11.12")
        base_node = ET.SubElement(root, "node", TEXT="home", ID="ID_HOME")
        ET.SubElement(base_node, "node", TEXT="Header", ID="ID_HEADER")

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(master_path, encoding="utf-8", xml_declaration=True)

        print("✅ New master mindmap created successfully.")

    print(f"🔍 Loading master mindmap: {master_path}")
    master_tree = ET.parse(master_path)
    master_root = master_tree.getroot()

    # --- Locate the Header node ---
    header_node = None
    for node in master_root.findall(".//node"):
        if normalize(node.attrib.get("TEXT", "")) == "header":
            header_node = node
            break

    if header_node is None:
        raise ValueError("❌ No 'Header' node found in master mindmap!")

    print("📂 Found 'Header' node. Starting smart merge...\n")

    # --- Iterate all mindmap files ---
    for file_name in os.listdir(mindmap_folder):
        if not file_name.lower().endswith(".mm"):
            continue
        if file_name.lower() in ["home.mm", "merged_website_structure.mm"]:
            continue

        page_name = os.path.splitext(file_name)[0].strip()
        normalized_page = normalize(page_name)

        sub_path = os.path.join(mindmap_folder, file_name)
        print(f"🔗 Processing {file_name} → {page_name}")

        try:
            sub_tree = ET.parse(sub_path)
            sub_root = sub_tree.getroot().find(".//node")

            if sub_root is None:
                print(f"⚠️ Skipped (no valid root node in {file_name})")
                continue

            # # --- Find matching header node (case-insensitive smart match) ---
            # target_node = None
            # for node in header_node.findall(".//node"):
            #     header_text = node.attrib.get("TEXT", "")
            #     if normalize(header_text) == normalized_page:
            #         target_node = node
            #         break

            # if target_node is None:
            #     print(f"⚠️ No matching header node found for '{page_name}'. Skipping merge.\n")
            #     continue
            normalized_page = normalize(page_name)
            target_node = find_matching_header(normalized_page, header_node)

            if target_node is None:
                print(f"⚠️ No matching header node found for '{page_name}'. Skipping merge.")
                continue


            # --- Merge children ---
            sub_children = sub_root.findall("./node")
            if not sub_children:
                print(f"⚠️ No subnodes found in {file_name}.\n")
                continue

            for child in sub_children:
                target_node.append(copy.deepcopy(child))

            print(f"✅ Merged '{page_name}' → {target_node.attrib.get('TEXT')}\n")

        except Exception as e:
            print(f"❌ Error merging {file_name}: {e}\n")

    # --- Save final merged mindmap ---
    ET.indent(master_tree, space="  ")
    master_tree.write(output_path, encoding="utf-8", xml_declaration=True)
    convert_links_in_mm(output_path,output_path)
    print(f"🎉 Merge complete!\n📄 Saved merged mindmap → {output_path}")


if __name__ == "__main__":
    merge_mindmaps(base_folder="comp360software")
