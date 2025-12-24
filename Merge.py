def generating_full_mindmapp(base_folder="."):
    import xml.etree.ElementTree as ET
    import os
    print("🔄 Merging 'After Login' mindmap into main mindmap...")
    # Input files
    main_file = os.path.join(base_folder, "Full_Website_Structure_with_screenshots.mm")
    login_file = os.path.join(base_folder, "Full_Website_Structure_After_Login_updated_with_Screenshot.mm")
    output_file = os.path.join(base_folder, "Merged_Website_Structure_after_login.mm")

    # Parse both mindmaps
    main_tree = ET.parse(main_file)
    login_tree = ET.parse(login_file)

    main_root = main_tree.getroot()
    login_root = login_tree.getroot()

    # Find the "Login" node in the main file
    login_node_main = None
    for node in main_root.iter("node"):
        if node.attrib.get("TEXT") == "Login" or node.attrib.get("TEXT") == "Sign up / Sign in" or node.attrib.get("TEXT") == "Login / Sign up":
            login_node_main = node
            break

    if login_node_main is None:
        print("⚠️ Could not find a node with TEXT='Login' in the main mindmap. Skipping merge.")
        # Exit gracefully if no login node is found
        return

    # Append all child nodes from the login mindmap root into the found Login node
    for child in list(login_root):
        login_node_main.append(child)

    # ✅ Rename Homepage → After Login Flow (inside Login node only)
    for child in login_node_main.iter("node"):
        text_value = child.attrib.get("TEXT", "").strip().lower()
        if text_value in ("homepage", "home page", "home"):
            child.set("TEXT", "After Login Flow")

    # Save merged output
    main_tree.write(output_file, encoding="utf-8", xml_declaration=True)

    print(f"✅ Merged mindmap saved as {output_file}")
    print("✔️ Any 'Homepage' or 'Home Page' node under 'Login' renamed to 'After Login Flow'.")

if __name__ == "__main__":
    print("🚀 Starting full mindmap generation...")
    generating_full_mindmapp(base_folder="340bpriceguide")