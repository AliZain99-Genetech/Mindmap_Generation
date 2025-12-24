#!/usr/bin/env python3
# --------------------------------------------------------------
#   extract_main_nav_after_login.py (ASYNC version with home_screenshot)
# --------------------------------------------------------------
import json
import os
import math
import time
import re
from typing import List, Dict
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PWTimeoutError

load_dotenv()

USERNAME = os.getenv("SITE_USERNAME", "")
PASSWORD = os.getenv("SITE_PASSWORD", "")
LOGIN_URL = "https://www.340bpriceguide.net/client-login"
AUTH_STATE_PATH = "auth_state.json"


# --------------------------------------------------------------
# Helpers (async)
# --------------------------------------------------------------
async def wait_for_login_fields(page, timeout=8000):
    username_field = None
    password_field = None

    username_selectors = [
        "#username", "input#username", "input[name='username']",
        "input[name*='user' i]", "input[id*='user' i]",
        "input[name*='email' i]", "input[type='email']",
        "input[placeholder*='email' i']"
    ]

    password_selectors = [
        "#password", "input#password", "input[name='password']",
        "input[type='password']", "input[id*='pass' i]"
    ]

    # Username
    for sel in username_selectors:
        try:
            await page.wait_for_selector(sel, timeout=timeout)
            el = await page.query_selector(sel)
            if el:
                username_field = el
                break
        except Exception:
            continue

    # Password
    for sel in password_selectors:
        try:
            await page.wait_for_selector(sel, timeout=timeout)
            el = await page.query_selector(sel)
            if el:
                password_field = el
                break
        except Exception:
            continue

    if not (username_field and password_field):
        raise RuntimeError("Login fields not found")

    return username_field, password_field


async def click_login_button(page):
    selectors = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Login')",
        "button:has-text('Sign In')",
        "button:has-text('Log In')",
        "input[value*='Login' i]"
    ]

    for sel in selectors:
        try:
            btn = page.locator(sel)
            if await btn.is_visible():
                await btn.click()
                return
        except Exception:
            continue

    raise RuntimeError("Login button not found")


def save_links(links: List[Dict], filename: str):
    clean = [
        l for l in links
        if l.get("href")
        and "logout" not in (l.get("text") or "").lower()
        and "logout" not in (l.get("href") or "").lower()
    ]
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
    print(f"Saved: {filename} → {len(clean)} links")


# --------------------------------------------------------------
# Extract clickables (sync JS executed via page.eval_on_selector_all)
# --------------------------------------------------------------
async def extract_from_container(page, container_sel: str):
    inner = f"{container_sel} a, {container_sel} button, {container_sel} [role='button'], {container_sel} [onclick]"
    raw = await page.eval_on_selector_all(
        inner,
        """els => els.map(el => ({
            text: (el.innerText || el.textContent || '').trim(),
            href: el.href || el.getAttribute('onclick') || el.getAttribute('data-url') || null
        })).filter(l => l.text)"""
    )
    # Dedup by (text, href)
    seen = set()
    uniq = []
    for l in raw:
        key = (l.get("text"), l.get("href"))
        if key not in seen:
            seen.add(key)
            uniq.append(l)
    return uniq


# --------------------------------------------------------------
# Async home screenshot (partitioned chunks) using authenticated context
# --------------------------------------------------------------
async def home_screenshot(url: str, output_folder: str, partition_height: int = 1500, scroll_increment: int = 400, scroll_pause: float = 0.2):
    """
    Uses auth_state.json to create a context, navigates to `url`,
    scrolls to trigger lazy-loading, and saves partitioned screenshots
    into output_folder (created if not present).
    """
    os.makedirs(output_folder, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Use saved auth_state if it exists
        storage = AUTH_STATE_PATH if os.path.exists(AUTH_STATE_PATH) else None
        context = await browser.new_context(storage_state=storage) if storage else await browser.new_context()
        page = await context.new_page()

        print(f"→ Navigating to {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=120000)
        await page.wait_for_timeout(1500)

        # get heights (guard with try/except)
        try:
            total_height = await page.evaluate("() => Math.max(document.documentElement.scrollHeight, document.body.scrollHeight)")
            page_width = await page.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
        except Exception as e:
            print(f"Could not compute dimensions: {e}")
            total_height = 2000
            page_width = 1200

        print(f"📏 Total page height: {total_height}px, width: {page_width}px")

        # Trigger lazy load by incremental scrolls
        for y in range(0, max(int(total_height), 1), scroll_increment):
            await page.evaluate(f"window.scrollTo(0, {y})")
            await page.wait_for_timeout(int(scroll_pause * 1000))

        # Ensure final scroll to bottom
        await page.evaluate(f"window.scrollTo(0, {total_height})")
        await page.wait_for_timeout(500)

        # Partition and capture screenshots
        num_screens = math.ceil(total_height / partition_height) if partition_height > 0 else 1
        print(f"🖼 Number of screenshots to capture: {num_screens}")
        paths = []
        for i in range(num_screens):
            top = i * partition_height
            height = min(partition_height, total_height - top) if total_height - top > 0 else partition_height

            # Set viewport for the chunk
            try:
                await page.set_viewport_size({"width": page_width, "height": max(200, height)})
            except Exception:
                # some pages may not like very large widths/heights; ignore if fails
                pass

            await page.evaluate(f"window.scrollTo(0, {top})")
            await page.wait_for_timeout(300)

            file_path = os.path.join(output_folder, f"chunk_{i+1:03d}.png")
            await page.screenshot(path=file_path, full_page=False)
            print(f"✅ Saved: {file_path}")
            paths.append(file_path)

        await context.close()
        await browser.close()
    print(f"   → {len(paths)} chunks captured")
    return paths


# --------------------------------------------------------------
# Main async extraction function (login + extract header links)
# --------------------------------------------------------------
async def extract_main_nav_after_login(AUTH_STATE,HEADER_FILE: str, LOGIN_URL: str, username: str, password: str, headless: bool = True):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, slow_mo=150)
        context = await browser.new_context()
        page = await context.new_page()

        print("Navigating to login page...")
        await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)

        # find and fill username/password
        u_field, p_field = await wait_for_login_fields(page)
        await u_field.fill(username)
        await p_field.fill(password)

        # optional checkbox (remember me)
        try:
            checkbox = page.locator("input[type='checkbox']:visible")
            if await checkbox.count() > 0:
                try:
                    await checkbox.first.check()
                except Exception:
                    pass
        except Exception:
            pass

        # click login
        await click_login_button(page)

        # wait after login
        try:
            await page.wait_for_load_state("networkidle", timeout=20000)
            print("Logged in successfully")
        except Exception:
            print("Login may be slow — continuing anyway")

        # ensure page scrolled / lazy loaded
        # simple scroll with small sleeps
        try:
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(500)
        except Exception:
            pass

        # Expand sidebar if present
        try:
            toggler = page.locator(".sidebar-toggler, .menu-toggler, [aria-expanded]")
            if await toggler.count() > 0 and await toggler.first.is_visible():
                try:
                    await toggler.first.click()
                    await page.wait_for_timeout(1200)
                    print("Sidebar toggled open")
                except Exception:
                    pass
        except Exception:
            pass

        # find header container via keywords
        HEADER_KEYWORDS = ["header", "top", "navbar", "nav", "menu"]
        pattern = "|".join(re.escape(k) for k in HEADER_KEYWORDS)
        sel = f"[class*='{pattern}' i], [id*='{pattern}' i]"
        header_sel = None
        try:
            await page.wait_for_selector(sel, timeout=3000)
            header_sel = sel
        except PWTimeoutError:
            header_sel = "header"

        print(f"Header container selector → {header_sel}")

        header_links = await extract_from_container(page, header_sel)
        save_links(header_links, HEADER_FILE)

        # Save authenticated storage state to disk
        try:
            await context.storage_state(path=AUTH_STATE_PATH)
            print(f"Saved login auth state → {AUTH_STATE_PATH}")
        except Exception as e:
            print(f"Warning: could not save storage state: {e}")

        await context.close()
        await browser.close()
        print("Main navigation links extracted successfully!")


# --------------------------------------------------------------
# CLI entrypoint (async)
# --------------------------------------------------------------
async def run_cli():
    if not USERNAME or not PASSWORD:
        raise RuntimeError("Set SITE_USERNAME and SITE_PASSWORD in .env")

    target_url = "https://www.340bpriceguide.net/"
    domain_folder = os.path.join(os.getcwd(), "340bpriceguide")
    os.makedirs(domain_folder, exist_ok=True)

    HEADER_FILE = os.path.join(domain_folder, "header_links_After_Login.json")
    output_folder = os.path.join(domain_folder, "screenshots_After_Login", "Home")
    os.makedirs(os.path.dirname(HEADER_FILE), exist_ok=True)
    os.makedirs(output_folder, exist_ok=True)

    # Run login + extract header links (authenticated)
    await extract_main_nav_after_login(HEADER_FILE, LOGIN_URL, USERNAME, PASSWORD, headless=True)

    # Use saved auth_state to take partitioned screenshots of home page
    await home_screenshot(target_url, output_folder)

    print("\nAll done.")

# # run
# if __name__ == "__main__":
#     import asyncio
#     asyncio.run(run_cli())
