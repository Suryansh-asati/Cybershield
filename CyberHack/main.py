import os
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

# === CONFIG ===
SAVE_DIR = "screenshots"
os.makedirs(SAVE_DIR, exist_ok=True)

DEFAULT_WAIT = 15

def create_chrome_driver(headless: bool | None = None):
    """Always open Chrome with your default profile directory."""
    options = Options()

    # ⚠️ Path to your real Chrome user data dir
    user_data_dir = r"C:\Users\asati\AppData\Local\Google\Chrome\User Data"
    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument("--profile-directory=Default")  # or Profile 1/2/etc if needed

    if headless:
        options.add_argument('--headless=new')

    # Stability flags
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-logging")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])

    return webdriver.Chrome(options=options)

def _element_present(driver, by, selector) -> bool:
    try:
        driver.find_element(by, selector)
        return True
    except NoSuchElementException:
        return False

def scrape_trending(driver):
    """Navigate to trending tab and extract trending topics."""
    url = "https://x.com/explore/tabs/trending"
    driver.get(url)

    wait = WebDriverWait(driver, DEFAULT_WAIT)
    try:
        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div[data-testid='trend']")))
    except TimeoutException:
        print("[ERROR] No trend items found. Possibly not logged in or layout changed.")
        return []

    # Scroll to load more
    for _ in range(3):
        try:
            ActionChains(driver).scroll_by_amount(0, 600).perform()
        except WebDriverException:
            driver.execute_script("window.scrollBy(0, 600);")
        time.sleep(1.2)

    items = driver.find_elements(By.CSS_SELECTOR, "div[data-testid='trend']")
    trending_list = []

    for item in items:
        spans = [s.text.strip() for s in item.find_elements(By.CSS_SELECTOR, "span") if s.text.strip()]
        topic_name = "Unknown"
        tweet_count = ""
        if spans:
            topic_name = spans[0]
            for s in spans[1:]:
                if any(k in s.lower() for k in ["posts", "tweets"]) or any(ch.isdigit() for ch in s):
                    tweet_count = s
                    break
        trending_list.append({"topic": topic_name, "tweets": tweet_count})

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    screenshot_path = os.path.join(SAVE_DIR, f"trending_{timestamp}.png")
    driver.save_screenshot(screenshot_path)
    print(f"[INFO] Screenshot saved: {screenshot_path}")
    print(f"[INFO] Collected {len(trending_list)} trend items.")
    return trending_list

if __name__ == "__main__":
    driver = create_chrome_driver()
    try:
        trends = scrape_trending(driver)
        print("\nTrending Topics:")
        for i, t in enumerate(trends, 1):
            print(f"{i}. {t['topic']} {'- ' + t['tweets'] if t['tweets'] else ''}")
    finally:
        driver.quit()

# === Notes ===
# - Close all Chrome windows before running, or you’ll hit “profile in use” errors.
# - If you want to keep your normal Chrome open, create a separate Chrome profile (say Profile 5)
#   and replace `--profile-directory=Default` with that name.
# - This method reuses your saved cookies/logins/extensions, so Twitter/X should already be logged in.
# - Ensure your ChromeDriver version matches your installed Chrome.
    