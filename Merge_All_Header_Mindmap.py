import os
import xml.etree.ElementTree as ET

import os
import xml.etree.ElementTree as ET

def merge_mindmaps(base_folder):
    """
    Merge all .mm mindmaps for a given domain into a single master mindmap.

    Example:
        base_folder = "example.com"
        → Reads from example.com/mindmaps/
        → Writes to example.com/Full_Website_Structure.mm
    """

    mindmap_folder = os.path.join(base_folder, "mindmaps")
    master_path = os.path.join(mindmap_folder, "home.mm")
    output_path = os.path.join(base_folder, "Full_Website_Structure.mm")

    # --- Validate paths ---
    if not os.path.exists(mindmap_folder):
        raise FileNotFoundError(f"❌ Mindmap folder not found: {mindmap_folder}")

    # --- Create master mindmap if it doesn't exist ---
    if not os.path.exists(master_path):
        print(f"⚠️ Master mindmap not found. Creating a new one at: {master_path}")
        
        # Create a default mindmap structure
        root = ET.Element("map", version="freeplane 1.11.12")
        base_node = ET.SubElement(root, "node", TEXT="home", ID="ID_HOME")
        ET.SubElement(base_node, "node", TEXT="Header", ID="ID_HEADER")
        
        # Save the new master mindmap
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(master_path, encoding="utf-8", xml_declaration=True)
        
        print("✅ New master mindmap created successfully.")

    print(f"🔍 Loading master mindmap: {master_path}")
    master_tree = ET.parse(master_path)
    master_root = master_tree.getroot()

    # --- Find the "Header" node in master mindmap ---
    header_node = None
    for node in master_root.findall(".//node"):
        if node.attrib.get("TEXT", "").strip().lower() == "header":
            header_node = node
            break

    if header_node is None:
        raise ValueError("❌ No 'Header' node found in master mindmap!")

    print("📂 Found 'Header' node. Beginning smart merge...")

    # --- Merge all other .mm files ---
    for file_name in os.listdir(mindmap_folder):
        if not file_name.lower().endswith(".mm"):
            continue
        if file_name.lower() in ["home.mm", "full_website_structure.mm"]:
            continue

        page_name = os.path.splitext(file_name)[0].strip()
        sub_path = os.path.join(mindmap_folder, file_name)

        print(f"\n🔗 Processing {file_name} → {page_name.title()}")

        try:
            sub_tree = ET.parse(sub_path)
            sub_root = sub_tree.getroot().find(".//node")

            if sub_root is None:
                print(f"⚠️ Skipped (no valid root node in {file_name})")
                continue

            # --- Find matching header node ---
            target_node = None
            for node in header_node.findall(".//node"):
                if node.attrib.get("TEXT", "").strip().lower() == page_name.lower():
                    target_node = node
                    break

            if target_node is None:
                print(f"⚠️ No matching header node found for '{page_name}'. Skipping merge.")
                continue

            # --- Append subnodes ---
            sub_children = sub_root.findall("./node")
            if not sub_children:
                print(f"⚠️ No subnodes found in {file_name}.")
                continue

            for child in sub_children:
                target_node.append(child)

            print(f"✅ Merged '{page_name}' into Header → {target_node.attrib.get('TEXT')}")

        except Exception as e:
            print(f"❌ Error merging {file_name}: {e}")

    # --- Save merged mindmap ---
    ET.indent(master_tree, space="  ")
    master_tree.write(output_path, encoding="utf-8", xml_declaration=True)

    print(f"\n✅ Full merged mindmap saved at: {output_path}")


# if __name__ == "__main__":
#     merge_mindmaps()
