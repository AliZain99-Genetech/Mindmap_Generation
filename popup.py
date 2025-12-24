# from playwright.sync_api import sync_playwright # type: ignore
# import json, time, os
# from dotenv import load_dotenv # type: ignore

# load_dotenv()

# def extract_header_links(username, password, base_folder=".", headless=False):
#     with sync_playwright() as p:
#         browser = p.chromium.launch(headless=headless, slow_mo=200)
#         context = browser.new_context()
#         page = context.new_page()

#         # Change this URL dynamically per site you target
#         target_site = "https://www.340bpriceguide.net/"
#         print(f"🌐 Navigating to {target_site}")
#         page.goto(target_site, wait_until="domcontentloaded")

#         # ✅ Step 1: Detect if there's a login button (possibly opening popup)
#         print("🔍 Looking for login button or form...")

#         login_selectors = [
#             "a:has-text('Login')",
#             "button:has-text('Login')",
#             "text=Log in",
#             "text=Sign in",
#             "text=My Account",
#         ]

#         login_found = None
#         for selector in login_selectors:
#             try:
#                 page.wait_for_selector(selector, timeout=4000)
#                 login_found = selector
#                 break
#             except:
#                 continue

#         if login_found:
#             print(f"✅ Found login trigger: {login_found}")
#             page.click(login_found)
#             time.sleep(2)  # let popup/modal load
#         else:
#             print("⚠️ No login button found — maybe already on login page")

#         # ✅ Step 2: Try detecting a visible username/password input
#         possible_user_selectors = [
#             "input[name='username']",
#             "input[id*='user']",
#             "input[id*='email']",
#             "input[type='email']",
#         ]
#         possible_pass_selectors = [
#             "input[name='password']",
#             "input[id*='pass']",
#             "input[type='password']",
#         ]

#         user_input = None
#         pass_input = None

#         for sel in possible_user_selectors:
#             try:
#                 page.wait_for_selector(f"{sel}:visible", timeout=5000)
#                 user_input = sel
#                 break
#             except:
#                 continue

#         for sel in possible_pass_selectors:
#             try:
#                 page.wait_for_selector(f"{sel}:visible", timeout=5000)
#                 pass_input = sel
#                 break
#             except:
#                 continue

#         if not user_input or not pass_input:
#             print("❌ Could not find login inputs — skipping login.")
#         else:
#             print(f"🧠 Filling login form: {user_input}, {pass_input}")
#             page.fill(user_input, username)
#             page.fill(pass_input, password)

#             # ✅ Step 3: Find and click submit button
#             submit_selectors = [
#                 "button[type='submit']",
#                 "button:has-text('Login')",
#                 "button:has-text('Sign in')",
#                 "input[type='submit']",
#             ]
#             for selector in submit_selectors:
#                 try:
#                     page.click(selector)
#                     break
#                 except:
#                     continue

#             # Wait for potential redirect or modal close
#             print("⏳ Waiting after login...")
#             page.wait_for_load_state("networkidle")
#             time.sleep(3)

#         # ✅ Step 4: Extract header links (works after login or guest)
#         print("🔗 Extracting header links...")
#         links = page.eval_on_selector_all(
#             "header a",
#             "els => els.map(e => ({text: e.innerText.trim(), href: e.href}))"
#         )

#         output_path = os.path.join(base_folder, "header_links_After_Login.json")
#         with open(output_path, "w", encoding="utf-8") as f:
#             json.dump(links, f, indent=2, ensure_ascii=False)

#         print(f"✅ Extracted {len(links)} header links → {output_path}")

#         browser.close()
# def clean_header_links(base_folder="."):
#     input_file = os.path.join(base_folder, "header_links_After_Login.json")
#     output_file = os.path.join(base_folder, "header_links_After_Login.json")
#     # Load the header links JSON
#     with open(input_file, "r", encoding="utf-8") as f:
#         links = json.load(f)

#     # Filter out entries where "text" is empty or only spaces
#     cleaned_links = [link for link in links if link["text"].strip()]

#     # Save the cleaned JSON
#     with open(output_file, "w", encoding="utf-8") as f:
#         json.dump(cleaned_links, f, indent=2, ensure_ascii=False)

#     print(f"✅ Cleaned {len(links) - len(cleaned_links)} invalid entries.")
#     print(f"💾 Saved cleaned links to {output_file}")


# def login_section(username=None, password=None, headless=False, base_folder="."):
#     from dotenv import load_dotenv # type: ignore
#     from Header_Links_Ectractor_After_Login import extract_header_links_and_screenshots
#     from Header_mindmaps_after_login import header
#     from Merge_all_header_mindmap_After_Login import merge_mindmaps
#     import asyncio
#     from Validation_Mindmap_After_login import validation_after_login
#     import os
#     load_dotenv()

#     # env_user = os.getenv("SITE_USERNAME")
#     # env_pass = os.getenv("SITE_PASSWORD")

#     # If credentials not provided, fall back to .env

#     if not username or not password:
#         raise ValueError("❌ Username and Password are required (either from input or .env).")

#     # extract_header_links(username, password, base_folder, headless=headless) #1
#     # clean_header_links(base_folder)
#     print("✅ Login section completed successfully")

#     print("########## start header_link_extractor after login #######")

#     extract_header_links_and_screenshots(username, password, base_folder, headless=headless) #2

#     print("######## Header mindmap after login ##########")
#     asyncio.run(header(base_folder=base_folder)) #3

#     print("######## Start Merging mindmap after login #########")
#     merge_mindmaps(base_folder=base_folder) # 4
#     print("Mindmapp after login merged Sucessfully")

#     print("###### Validating after login ##########")
#     validation_after_login(base_folder=base_folder) #5

   

#     print("Fully Mindmapp is created")

# if __name__ == "__main__":
#     extract_header_links(username="Ali", password="123456", headless=False)
#     clean_header_links(input_file="output\header_links_After_Login.json",output_file="output\header_links_After_Login.json")
