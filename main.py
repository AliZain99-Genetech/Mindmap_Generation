# ------------------------------------------------------------------------------
# Standard library imports
# ------------------------------------------------------------------------------
import json
import asyncio
import logging
import os
import sys
import traceback

# ------------------------------------------------------------------------------
# Third-party imports
# ------------------------------------------------------------------------------
from dotenv import load_dotenv
from flask import (
    Flask,
    request,
    jsonify,
    render_template,
    send_from_directory,
    abort
)
# from flask_socketio import SocketIO
from extractors import (
    extract_domain,
    extract_header_links as extract_all_links_with_submenus,
    home_screenshot,
    extract_links_from_header_json,
    extract_links,
)
from mindmap_generators import (
    home_page,
    generate_mindmaps_from_headers,
    merge_mindmaps,
)
from post_processing import (
    Screenshot_Node,
    testcases,
    merge_testcases_into_full,
    screenshot_if_404,
    zip_folder,
    process_mindmap,
)
from extractor_after_login import (
extract_main_nav_after_login,
home_screenshot as home_screenshot_after_login,
extract_header_links_and_screenshots,
extract_home_link,
)
from mindmap_generators_after_login import (
    header,
    home_page as home_page_after_login,
    merge_mindmaps as merge_mindmaps_after_login,
)
# ------------------------------------------------------------------------------
# Local application imports
# ------------------------------------------------------------------------------
from log_emitter import setup_logging, socketio

# ------------------------------------------------------------------------------
# Environment & Event Loop Setup
# ------------------------------------------------------------------------------
load_dotenv()
# CRITICAL: Use ProactorEventLoop for Windows + Playwright subprocess support
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# ------------------------------------------------------------------------------
# Flask App Initialization
# ------------------------------------------------------------------------------

app = Flask(__name__, static_folder='static', static_url_path='/static')
# Set the logging level for socketio and engineio to WARNING to reduce verbosity
logging.getLogger('socketio').setLevel(logging.WARNING)
logging.getLogger('engineio').setLevel(logging.WARNING)


setup_logging(app)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/<path:path>')
def static_files(path):
    return send_from_directory('static', path)

@app.route('/extract', methods=['POST'])
def extract():
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
    
    url = data.get('url')

    username = data.get("username","").strip()
    password = data.get("password","").strip()
    login_url= data.get("login_url","").strip()


    if not url:
        return jsonify({'error': 'URL is required'}), 400

    try:
        logging.info(f"Extracting links from: {url}")
        logging.info(f"logging url {login_url}")
        folder_name = extract_domain(url)
        folder_name = f"{folder_name}"
        logging.info("Creating Folder with domain name")
        if not os.path.exists(folder_name):
            os.mkdir(folder_name)
            os.makedirs(os.path.join(folder_name,"headers"), exist_ok=True)
            logging.info(f"folder created with {folder_name} name")
        else:
            logging.info(f"!!!!!!!!!!!!!!!!!!! {folder_name} folder already created!!!!!!!!!!!!!")
        # Run the new extractor function
        json_file_path = os.path.join(folder_name, "header_links.json")
        output_folder = os.path.join(folder_name,"screenshot/home")
        home_screenshot(url, output_folder)
        home_link=extract_links(url)
        output_file=os.path.join(folder_name, "home_page_link.json")
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(home_link, f, indent=2)
        logging.info("Home page links and screenshot captured.")
        Screenshot_folder=os.path.join(folder_name,"screenshot/home")
        output_mm_file=os.path.join(folder_name,"mindmaps/home.mm")
        logging.info("Home page mindmap generated.")
        extract_all_links_with_submenus(url, headless=True, output_file=json_file_path)
        # Load the links from the generated file to return them in the response
        print(f" folder {json_file_path}")
        # os.makedirs(json_file_path, exist_ok=True)
        with open(json_file_path, "r", encoding="utf-8") as f:
            cleaned_links = json.load(f)
        
        logging.info(f"Successfully extracted {len(cleaned_links)} links.")
        input_file = json_file_path
        try:
            logging.info("🚀 Starting header link extraction process...")

            # --- Extract header links ---
            extract_links_from_header_json(header_json_path=input_file, base_folder=folder_name)
            logging.info("✅ Header links extracted successfully.")

            # --- Determine domain folder from input file ---
            domain_folder = os.path.dirname(input_file)
            if not domain_folder:
                domain_folder = "."

            # --- Define headers folder path ---
            headers_folder = os.path.join(domain_folder, "headers")
            extracted_header_path=os.path.join(domain_folder,"header_links.json")
            output_folder=os.path.join(domain_folder,"mindmaps")
            screenshot_folder=os.path.join(domain_folder,"screenshot")
            home_screenshot_folder=os.path.join(screenshot_folder,"home")
            home_file=os.path.join(domain_folder,"home_page_link.json")
            output_mm_file=os.path.join(domain_folder,"mindmaps","home.mm")
            # --- Check if headers folder exists ---
            if os.path.isdir(headers_folder):
                logging.info(f"📂 Found headers folder {headers_folder}. Starting MindMap generation...")

                # 🧠 Generate MindMaps for all header link files
                asyncio.run(generate_mindmaps_from_headers(headers_folder,extracted_header_path,output_folder,screenshot_folder))
                logging.info("✅ MindMaps created from header links.")
                logging.info("✅ making home mindmap")
                asyncio.run( home_page(home_screenshot_folder,home_file,output_mm_file))
                logging.info("✅ done home mindmap")
                # 🔗 Merge all generated MindMaps
                logging.info("🔄 Merging all header MindMaps...")
                merge_mindmaps(base_folder=domain_folder)
                logging.info("✅ Merged all header MindMaps successfully.")

                # ✅ Validate the final merged structure
                logging.info("🧩 Starting validation...")
                # validation(base_folder=folder_name)
                logging.info("✅ Validation complete.")

                # 🖼️ Take screenshots of nodes
                logging.info("📸 Capturing screenshots for MindMap nodes...")
                asyncio.run(Screenshot_Node(base_folder=folder_name))
                logging.info("✅ Screenshots integrated into MindMap.")

                # 👤 Handle login-related processing if credentials provided
                if username and password:
                    logging.info("🔐 Starting login section...")
                    from ScreenShot_node_After_Login import login_and_get_context
                    from playwright.async_api import async_playwright # type: ignore
                    AUTH_STATE=os.path.join(domain_folder,"auth_state.json")

                    async def main_login():
                        async with async_playwright() as p:
                            browser, context = await login_and_get_context(AUTH_STATE,login_url,p, username, password, headless=True)
                            if context:
                                # from Validation_Mindmap_After_login import validation_after_login
                                logging.info("context found ")
                                output_folder = os.path.join(domain_folder, "screenshots_After_Login", "Home")
                                HEADER_FILE=os.path.join(domain_folder,"header_links_After_Login.json")
                                HEADERS_FOLDER=os.path.join(domain_folder,"headers_After_Login")
                                home_path=os.path.join(domain_folder,"home_page_links_after_login.json")
                                SCREENSHOT_FOLDER=os.path.join(domain_folder,"screenshots_After_Login")
                                MINDMAP_FOLDER = os.path.join(domain_folder,"mindmaps_After_Login")
                                output_mm_file= os.path.join(MINDMAP_FOLDER,"home.mm")
                                # await extract_main_nav_after_login(AUTH_STATE,HEADER_FILE, login_url, username, password, headless=True)
                                # await home_screenshot_after_login(url,output_folder)
                                # await extract_header_links_and_screenshots(url,AUTH_STATE,HEADERS_FOLDER)
                                logging.info("Bhai yahan hu ma home ka mindmap bna rha hu")
                                # await extract_home_link(AUTH_STATE,url,home_path)
                                # await header(url,HEADERS_FOLDER,SCREENSHOT_FOLDER,MINDMAP_FOLDER)
                                logging.info("moving towards homepage")
                                # await home_page_after_login(output_folder,home_path,output_mm_file)
                                logging.info(f"domain folder  is {domain_folder}")
                                merge_mindmaps_after_login(base_folder=domain_folder)
                                # validation_after_login(base_folder=domain_folder)
                            await browser.close()

                    asyncio.run(main_login())

                    logging.info("📸 Capturing screenshots after login...")
                    from ScreenShot_node_After_Login import Screenshot
                    # asyncio.run(Screenshot(url,username=username, password=password, base_folder=domain_folder, headless=True))
                    logging.info("✅ Screenshots after login captured.")

                    # 🧠 Merge all MindMaps into a single file
                    logging.info("🔄 Merging all MindMaps into one unified file...")
                    from merge import generating_full_mindmapp
                    generating_full_mindmapp(base_folder=domain_folder)
                    logging.info("✅ Unified MindMap generated.")

                    # 📝 Add button descriptions
                    logging.info("🧾 Adding button descriptions to final MindMap...")
                    
                    INPUT_MM = os.path.join(domain_folder, "Merged_Website_Structure_after_login.mm")
                    OUTPUT_MM = os.path.join(domain_folder, "Full_Website_Structure_updated_with_descriptions.mm")

                    if not os.path.exists(INPUT_MM):
                        logging.info(f"❌ {INPUT_MM} file not found.")
                    else:
                        process_mindmap(INPUT_MM, OUTPUT_MM)
                        logging.info("✅ Button descriptions added successfully.")
                        final_output_path= os.path.join(domain_folder, "Generated_TestCases.mm")
                        raw_output_path=os.path.join(domain_folder, "raw_model_output.mm") 
                        header_links=os.path.join(domain_folder, "header_links.json")
                        print(f"output file {raw_output_path}")                          
                        testcases(OUTPUT_MM,raw_output_path,final_output_path,header_links)
                        merge_testcases_into_full(OUTPUT_MM,final_output_path,os.path.join(domain_folder, "Full_Website_Structure_updated_with_descriptions_and_testCases.mm"))
                        logging.info("✅ Test cases merged successfully.")
                        test_url=url+"abc" # Example URL that gives 404
                        screenshot_if_404(test_url,base_folder=domain_folder)

                        # --- Zip the entire folder after final file creation ---
                        try:
                            output_zip_file = f"{folder_name}.zip"
                            logging.info(f"output zip file is {output_zip_file}")
                            logging.info(f"folder_name{folder_name}")
                            zip_folder(folder_name, output_zip_file)
                            logging.info(f"✅ Successfully zipped the folder to {output_zip_file}")
                        except Exception as e:
                            logging.info(f"❌ Error during zipping: {e}")
                            return jsonify({
                                'error': f"Failed to zip the folder: {e}",
                                'details': traceback.format_exc()
                            }), 500

                else:
                    logging.info("⚠️ No username/password provided — skipping login section.")
                    # --- Zip the folder if no login is provided ---
                    print(f" domain folder is {domain_folder}")
                    
                    INPUT_MM = os.path.join(domain_folder, "Full_Website_Structure_with_screenshots.mm")
                    OUTPUT_MM = os.path.join(domain_folder, "Full_Website_Structure_updated_with_descriptions.mm")
                    print(f"input file {INPUT_MM}")
                    if not os.path.exists(INPUT_MM):
                        logging.info(f"❌ {INPUT_MM} file not found.")
                    else:
                        process_mindmap(INPUT_MM, OUTPUT_MM)
                        logging.info("✅ Button descriptions added successfully.")
                        final_output_path= os.path.join(domain_folder, "Generated_TestCases.mm")
                        raw_output_path=os.path.join(domain_folder, "raw_model_output.mm") 
                        header_links=os.path.join(domain_folder, "header_links.json")
                        print(f"output file {raw_output_path}")                          
                        testcases(OUTPUT_MM,raw_output_path,final_output_path,header_links)
                        merge_testcases_into_full(OUTPUT_MM,final_output_path,os.path.join(domain_folder, "Full_Website_Structure_updated_with_descriptions_and_testCases.mm"))
                        logging.info("✅ Test cases merged successfully.")
                        test_url=url+"abc" # Example URL that gives 404
                        screenshot_if_404(test_url,base_folder=domain_folder)
                    try:
                        output_zip_file = f"{folder_name}.zip"
                        zip_folder(folder_name, output_zip_file)
                        logging.info(f"✅ Successfully zipped the folder to {output_zip_file}")
                    except Exception as e:
                        logging.info(f"❌ Error during zipping: {e}")
                        return jsonify({
                            'error': f"Failed to zip the folder: {e}",
                            'details': traceback.format_exc()
                        }), 500

            else:
                logging.info(f"❌ Headers folder not found at path: {headers_folder}")

        except Exception as e:
            error_msg = f"An error occurred during MindMap generation: {str(e)}"
            logging.error(f"❌ {error_msg}")
            logging.error(traceback.format_exc())
            return jsonify({
                'error': error_msg,
                'details': traceback.format_exc()
            }), 500

    except Exception as e:
        error_msg = f"An unexpected error occurred: {str(e)}"
        logging.error(f"Error during extraction: {error_msg}")
        logging.error(traceback.format_exc())
        return jsonify({
            'error': error_msg,
            'details': traceback.format_exc()
        }), 500

    # ✅ Return cleaned result to API response
    return jsonify({
        'success': True,
        'count': len(cleaned_links),
        'links': cleaned_links,
        'zip_file': f"{folder_name}.zip"
    })
    
@app.route('/download/<filename>')
def download_file(filename):
    logging.info (os.getcwd())
    return send_from_directory(os.getcwd(), filename, as_attachment=True)



if __name__ == '__main__':
    socketio.run(app,host='0.0.0.0', debug=True, use_reloader=False,allow_unsafe_werkzeug=True,port=9000)
    

    

