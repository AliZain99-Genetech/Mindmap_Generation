import xml.etree.ElementTree as ET

def indent(elem, level=0):
    i = "\n" + level * "  "
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for child in elem:
            indent(child, level + 1)
        if not elem.tail or not elem.tail.strip():
            elem.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def merge_testcases_into_full(full_mindmap_path, testcase_mindmap_path, output_path):
    full_tree = ET.parse(full_mindmap_path)
    full_root = full_tree.getroot()

    test_tree = ET.parse(testcase_mindmap_path)
    test_root = test_tree.getroot()

    # Find first top-level node in full mindmap
    parent_nodes = full_root.findall("./node")
    if not parent_nodes:
        raise ValueError("❌ No top-level <node> in full mindmap.")
    parent_node = parent_nodes[0]

    # Get testcases root node
    testcase_main_node = test_root.find("./node")
    if testcase_main_node is None:
        raise ValueError("❌ No <node> root found in testcase mindmap.")

    # Deep clone
    def clone(node):
        new = ET.Element("node", node.attrib)
        for child in node:
            new.append(clone(child))
        return new

    cloned = clone(testcase_main_node)

    # Merge
    parent_node.append(cloned)

    # Pretty format
    indent(full_root)

    full_tree.write(output_path, encoding="UTF-8", xml_declaration=True)
    print(f"✅ Pretty formatted merged mindmap saved to {output_path}")
if __name__ == "__main__":
    full_mindmap_path = r"comp360software\Full_Website_Structure_updated_with_descriptions.mm"
    testcase_mindmap_path = r"comp360software\Generated_TestCases.mm"
    output_path = r"comp360software\Full_Website_Structure_updated_with_descriptions_and_testCases.mm"
    merge_testcases_into_full(full_mindmap_path, testcase_mindmap_path, output_path)