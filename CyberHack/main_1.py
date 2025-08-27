import os
import time
import json
import csv
from datetime import datetime
from typing import List, Dict, Optional, Iterable
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    StaleElementReferenceException,
)

# === CONFIG ===
SAVE_DIR = "screenshots"
SCROLL_ATTEMPTS = 5
SCROLL_PAUSE_SEC = 1.2
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Firefox/118.0 Safari/537.36"
)
os.makedirs(SAVE_DIR, exist_ok=True)

# Credentials (use environment variables to avoid hard coding!)
TWITTER_USERNAME = os.environ.get("TWITTER_USERNAME")  # email / username / phone
TWITTER_PASSWORD = os.environ.get("TWITTER_PASSWORD")


def _dump_debug_state(driver: webdriver.Firefox, tag: str):
    """Dump minimal diagnostics to help troubleshoot failures."""
    try:
        os.makedirs(SAVE_DIR, exist_ok=True)
        debug_file = os.path.join(SAVE_DIR, f"debug_{tag}.txt")
        with open(debug_file, "w", encoding="utf-8") as f:
            f.write(f"URL: {driver.current_url}\n")
            f.write(f"Title: {driver.title}\n")
            src = driver.page_source
            if len(src) > 20000:
                src = src[:20000] + "\n...[truncated]"
            f.write(src)
        driver.save_screenshot(os.path.join(SAVE_DIR, f"debug_{tag}.png"))
        print(f"🛠 Debug artifacts saved with tag '{tag}'.")
    except Exception as e:
        print(f"⚠️ Failed to dump debug state ({tag}): {e}")

def create_firefox_driver(
    profile_path: Optional[str] = None,
    headless: bool = False,
    binary_path: Optional[str] = None,
    geckodriver_log: str = "geckodriver.log",
) -> webdriver.Firefox:
    """Create a Firefox WebDriver instance with resilience & diagnostics.

    Tries normal mode, then (if failure and not already) retries headless.
    Allows specifying existing Firefox profile (to keep login) and custom binary path.
    """
    from selenium.common.exceptions import WebDriverException

    def _build_options(_headless: bool) -> FirefoxOptions:
        opts = FirefoxOptions()
        if _headless:
            opts.add_argument("-headless")
        # Accept binary path via param or env var FIREFOX_BIN
        firefox_bin = binary_path or os.environ.get("FIREFOX_BIN")
        if firefox_bin:
            opts.binary_location = firefox_bin
        if profile_path and os.path.isdir(profile_path):
            opts.profile = profile_path
        # User agent override (helps with some bot-detection variants / layout flags)
        try:
            opts.set_preference("general.useragent.override", USER_AGENT)
        except Exception:
            pass
        return opts

    attempts = []
    tried_headless = headless
    for attempt in range(2):
        opts = _build_options(headless if attempt == 0 else True)
        mode = "headless" if (headless if attempt == 0 else True) else "normal"
        try:
            service = FirefoxService(log_path=geckodriver_log)
            driver = webdriver.Firefox(options=opts, service=service)
            try:
                driver.maximize_window()
            except Exception:
                pass
            if attempt == 1 and not tried_headless:
                print("Retried Firefox in headless mode successfully.")
            return driver
        except WebDriverException as e:
            attempts.append((mode, str(e)))
            # If already tried headless or initial request was headless, break
            if headless or attempt == 1:
                break
            print("Firefox start failed, retrying in headless mode...")
            continue

    # If we reach here, all attempts failed
    msg_lines = ["Failed to start Firefox WebDriver. Attempts:"]
    for mode, err in attempts:
        snippet = err.splitlines()[0]
        msg_lines.append(f" - {mode}: {snippet}")
    msg_lines.append("Hints: \n  * Ensure Firefox is installed and matches system architecture (64-bit)."
                     "\n  * Update selenium: pip install -U selenium."
                     "\n  * Remove/rename a corrupt profile folder if used."
                     "\n  * If corporate security blocks, try headless or different user profile."
                     "\n  * Set FIREFOX_BIN env var if Firefox not on default path.")
    raise RuntimeError("\n".join(msg_lines))


def _parse_trend_block(block_text: str) -> Dict[str, str]:
    """Heuristically parse a trend block's text into topic + tweets/posts count.

    Twitter/X trend blocks typically have multiple lines, e.g.:
        Trending in Technology
        Quantum Computing
        12.3K posts

    We skip lines starting with 'Trending' (case-insensitive) or containing a middle dot used as separators.
    """
    lines = [l.strip() for l in block_text.splitlines() if l.strip()]
    topic = ""
    tweets = ""
    for line in lines:
        low = line.lower()
        if low.startswith("trending"):
            continue
        if " · " in line:
            continue
        # first acceptable becomes topic
        if not topic:
            topic = line
            continue
    # find a posts / tweets line
    for line in lines:
        low = line.lower()
        if ("tweets" in low or "posts" in low) and any(ch.isdigit() for ch in line):
            tweets = line
            break
    return {"topic": topic or "Unknown", "tweets": tweets}

def scrape_trending(driver: webdriver.Firefox) -> List[Dict[str, str]]:
    """Scrape trending topics from Twitter/X Explore page.

    Returns list of dicts: { 'topic': str, 'tweets': str }.
    """
    # Try both legacy twitter.com and new x.com domains
    trend_paths = [
        "https://x.com/explore/tabs/trending",
        "https://twitter.com/explore/tabs/trending",
    ]
    last_exc = None
    for url in trend_paths:
        try:
            driver.get(url)
            time.sleep(1)
            break
        except Exception as e:
            last_exc = e
    else:
        print(f"❌ Failed to navigate to any trending URL: {last_exc}")
        return []

    # Detect login redirect early
    if "login" in driver.current_url.lower():
        print("❌ Redirected to login page — cannot collect trends.")
        return []

    wait = WebDriverWait(driver, 15)
    try:
        # Wait until at least one trend block OR a fallback marker (e.g., Explore heading)
        wait.until(
            lambda d: d.find_elements(By.XPATH, "//div[@data-testid='trend']")
            or d.find_elements(By.XPATH, "//h2[contains(translate(., 'EXPLORE', 'explore'), 'explore')]")
        )
    except TimeoutException:
        print("❌ Initial wait timed out: no trend elements or explore heading.")
        _dump_debug_state(driver, "initial_wait_failure")
        return []

    prev_count = 0
    for attempt in range(SCROLL_ATTEMPTS):
        try:
            elements = driver.find_elements(By.XPATH, "//div[@data-testid='trend']")
        except Exception:
            elements = []
        current_count = len(elements)
        if current_count >= prev_count + 1:
            prev_count = current_count
        else:
            # Attempt to scroll to load more
            driver.execute_script("window.scrollBy(0, 800);")
            try:
                wait.until(lambda d: len(d.find_elements(By.XPATH, "//div[@data-testid='trend']")) > prev_count)
                prev_count = len(driver.find_elements(By.XPATH, "//div[@data-testid='trend']"))
            except TimeoutException:
                # No more items loaded; break early
                break
        time.sleep(SCROLL_PAUSE_SEC)

    # Recollect final elements (avoid stale references)
    trend_elements = driver.find_elements(By.XPATH, "//div[@data-testid='trend']")
    trends: List[Dict[str, str]] = []
    for el in trend_elements:
        try:
            text = el.text
            trends.append(_parse_trend_block(text))
        except (StaleElementReferenceException, NoSuchElementException):
            trends.append({"topic": "Unknown", "tweets": ""})

    screenshot_path = os.path.join(SAVE_DIR, "twitter_trending_full.png")
    if driver.save_screenshot(screenshot_path):
        print(f"✅ Screenshot saved: {screenshot_path}")
    else:
        print("⚠️ Screenshot failed to save.")

    if not trends:
        print("⚠️ No trends parsed; dumping debug state.")
        _dump_debug_state(driver, "no_trends_found")

    return trends


def login_to_twitter(driver: webdriver.Firefox, username: str, password: str, timeout: int = 30) -> bool:
    """Log into Twitter/X using provided username and password.

    Returns True if login appears successful, False otherwise.
    NOTE: This will not handle additional verification challenges (2FA, email/SMS, CAPTCHA).
    """
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException

    # Try new x.com domain first, then fallback
    login_urls = ["https://x.com/i/flow/login", "https://twitter.com/i/flow/login"]
    for lu in login_urls:
        try:
            driver.get(lu)
            break
        except Exception:
            continue
    wait = WebDriverWait(driver, timeout)

    try:
        # Step 1: username / email / phone
        user_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='text']")))
        user_input.clear()
        user_input.send_keys(username)
        user_input.send_keys(Keys.ENTER)
    except TimeoutException:
        print("❌ Username input not found.")
        return False

    # Sometimes Twitter asks to confirm the username again or asks for email if ambiguous.
    # We'll attempt to detect password field; if not present, handle potential second prompt.
    try:
        wait.until(lambda d: d.find_element(By.CSS_SELECTOR, "input[name='password']") or d.find_elements(By.CSS_SELECTOR, "input[name='text']"))
    except TimeoutException:
        print("❌ Neither password nor second identifier prompt appeared.")
        return False

    # If a second text input still present with no password yet (Edge case: confirm username)
    if not driver.find_elements(By.CSS_SELECTOR, "input[name='password']") and driver.find_elements(By.CSS_SELECTOR, "input[name='text']"):
        try:
            second_input = driver.find_element(By.CSS_SELECTOR, "input[name='text']")
            if second_input.get_attribute('value') == "":
                second_input.send_keys(username)
                second_input.send_keys(Keys.ENTER)
        except Exception:
            pass

    try:
        pwd_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='password']")))
        pwd_input.clear()
        pwd_input.send_keys(password)
        pwd_input.send_keys(Keys.ENTER)
    except TimeoutException:
        print("❌ Password input not found.")
        return False

    # Wait for a known post-login element OR redirect away from flow/login
    try:
        wait.until(lambda d: "login" not in d.current_url.lower())
    except TimeoutException:
        print("⚠️ Still on login page; login may have failed or requires additional verification.")
        return False

    # Basic heuristic: presence of main navigation (Home link) or trend container
    if driver.find_elements(By.XPATH, "//a[@href='/home']") or driver.find_elements(By.XPATH, "//div[@data-testid='trend']"):
        print("✅ Login likely successful.")
        return True
    print("⚠️ Login uncertain (no expected elements found).")
    return False


def export_trends(
    trends: List[Dict[str, str]],
    formats: Iterable[str],
    base_name: str = "trending",
    directory: str = SAVE_DIR,
    timestamp: bool = True,
) -> List[str]:
    """Export trends to selected formats.

    formats: any of {'json','csv','md','txt'}
    Returns list of file paths created.
    """
    os.makedirs(directory, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ") if timestamp else ""
    suffix = f"_{ts}" if ts else ""
    created = []
    safe_base = base_name.replace(os.sep, "_")

    if not trends:
        print("ℹ️ No trends to export.")
        return []

    if "json" in formats:
        path = os.path.join(directory, f"{safe_base}{suffix}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(trends, f, ensure_ascii=False, indent=2)
        created.append(path)
    if "csv" in formats:
        path = os.path.join(directory, f"{safe_base}{suffix}.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["topic", "tweets"])
            writer.writeheader()
            writer.writerows(trends)
        created.append(path)
    if "txt" in formats:
        path = os.path.join(directory, f"{safe_base}{suffix}.txt")
        with open(path, "w", encoding="utf-8") as f:
            for i, row in enumerate(trends, 1):
                f.write(f"{i}. {row['topic']} | {row['tweets']}\n")
        created.append(path)
    if "md" in formats:
        path = os.path.join(directory, f"{safe_base}{suffix}.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Trending Topics ({datetime.utcnow().isoformat()}Z)\n\n")
            f.write("| # | Topic | Tweets/Posts |\n|---|-------|-------------|\n")
            for i, row in enumerate(trends, 1):
                f.write(f"| {i} | {row['topic'].replace('|','/')} | {row['tweets'].replace('|','/')} |\n")
        created.append(path)

    for p in created:
        print(f"💾 Exported: {p}")
    return created

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape Twitter/X trending topics (Firefox)")
    parser.add_argument("--headless", action="store_true", help="Run Firefox in headless mode")
    parser.add_argument("--profile", type=str, default=None, help="Path to Firefox profile to reuse session")
    parser.add_argument(
        "--export-formats",
        type=str,
        default="json,csv",
        help="Comma-separated formats to export: json,csv,txt,md",
    )
    parser.add_argument("--no-timestamp", action="store_true", help="Don't add timestamp suffix to export files")
    parser.add_argument("--base-name", type=str, default="trending", help="Base filename for exports")
    args = parser.parse_args()

    driver = None
    FIREFOX_PROFILE_PATH = args.profile
    try:
        driver = create_firefox_driver(profile_path=FIREFOX_PROFILE_PATH, headless=args.headless)

        logged_in = False
        if TWITTER_USERNAME and TWITTER_PASSWORD:
            print("ℹ️ Attempting login with provided credentials...")
            logged_in = login_to_twitter(driver, TWITTER_USERNAME, TWITTER_PASSWORD)
        else:
            print("ℹ️ Set TWITTER_USERNAME and TWITTER_PASSWORD environment variables to auto-login.")

        trends: List[Dict[str, str]] = []
        if logged_in or FIREFOX_PROFILE_PATH:
            trends = scrape_trending(driver)
        else:
            print("ℹ️ Skipping scrape because not logged in and no profile path provided. Set credentials or --profile to enable scraping.")
        if not trends and logged_in:
            # Only retry if we were authenticated
            trends = scrape_trending(driver)

        print("\n🔥 Trending Topics (Firefox):")
        for i, t in enumerate(trends, 1):
            print(f"{i}. {t['topic']} - {t['tweets']}")

        export_formats = [f.strip().lower() for f in args.export_formats.split(',') if f.strip()]
        export_trends(trends, export_formats, base_name=args.base_name, timestamp=not args.no_timestamp)
    finally:
        if driver:
            driver.quit()


