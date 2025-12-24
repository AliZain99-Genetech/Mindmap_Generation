import zipfile
import os

def zip_folder(folder_path, output_path):
    """
    Zips the contents of an entire folder (including subfolders)
    into a single ZIP file.

    Args:
        folder_path (str): Path to the folder to be zipped.
        output_path (str): Output path for the ZIP file (including filename.zip)
    """
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, folder_path)
                zipf.write(abs_path, rel_path)
    print(f"✅ Folder '{folder_path}' zipped successfully to '{output_path}'")

# Example usage
if __name__ == "__main__":
    folder_to_zip = r"generated_mindmaps\340bpriceguide"
    output_zip_file = r"generated_mindmaps\340bpriceguide.zip"
    zip_folder(folder_to_zip, output_zip_file)
