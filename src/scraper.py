import os
import sys
import time
import random
from pathlib import Path
from typing import Optional, Dict, Any, List

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, TimeoutError as PlaywrightTimeoutError
from loguru import logger
from src.config import config
from src.extractor import PostExtractor



class LinkedInScraper:
    """Automates headless browser to scrape recent activity from LinkedIn profile."""

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    )

    def __init__(self, headless: Optional[bool] = None):
        self.headless = config.headless if headless is None else headless
        self.session_file = config.session_file
        self.activity_url = config.linkedin_activity_url

    def _get_stealth_context(self, browser: Browser, is_login_flow: bool = False) -> BrowserContext:
        """Creates a browser context configured with stealth attributes and saved session cookies."""
        storage_state = str(self.session_file) if (self.session_file.exists() and not is_login_flow) else None

        context = browser.new_context(
            user_agent=self.USER_AGENT,
            viewport={"width": 1440, "height": 900},
            locale="tr-TR",
            timezone_id="Europe/Istanbul",
            storage_state=storage_state,
            extra_http_headers={
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
                "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
            },
        )

        # Inject li_at cookie if provided via environment and not in interactive login flow
        if not storage_state and not is_login_flow and config.linkedin_li_at:
            li_at_val = config.linkedin_li_at.strip().strip('"').strip("'")
            if len(li_at_val) < 40:
                logger.warning(
                    f"⚠️ .env dosyasındaki LINKEDIN_LI_AT çerezi çok kısa görünüyor ({len(li_at_val)} karakter). "
                    "LinkedIn li_at çerezleri genellikle 150+ karakterdir. Lütfen tam çerez değerini kopyaladığınızdan emin olun veya 'python main.py --login' kullanın."
                )
            logger.info("Injecting li_at session cookie from configuration...")
            context.add_cookies([
                {
                    "name": "li_at",
                    "value": li_at_val,
                    "domain": ".linkedin.com",
                    "path": "/",
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "Lax",
                },
                {
                    "name": "JSESSIONID",
                    "value": '"ajax:0000000000000000000"',
                    "domain": ".linkedin.com",
                    "path": "/",
                    "httpOnly": False,
                    "secure": True,
                    "sameSite": "Lax",
                }
            ])

        # Apply stealth evasion scripts
        context.add_init_script("""
            // Mask webdriver
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            // Mock languages
            Object.defineProperty(navigator, 'languages', { get: () => ['tr-TR', 'tr', 'en-US', 'en'] });
            // Mock window.chrome
            window.chrome = { runtime: {} };
        """)

        return context

    def interactive_login(self) -> bool:
        """
        Launches a visible browser window allowing the user to log in once.
        Saves session cookies to session.json upon successful login.
        """
        logger.info("Starting interactive LinkedIn login session...")
        self.session_file.parent.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--start-maximized"]
            )
            context = self._get_stealth_context(browser, is_login_flow=True)
            page = context.new_page()

            logger.info("Opening LinkedIn login page...")
            page.goto("https://www.linkedin.com/login", timeout=60000)

            print("\n" + "=" * 70)
            print(" 👉 Lütfen açılan tarayıcıda LinkedIn hesabınıza giriş yapın.")
            print(" 👉 Giriş tamamlandıktan sonra oturum otomatik olarak kaydedilecektir.")
            print("=" * 70 + "\n")

            try:
                # Active polling for login completion & li_at cookie
                logger.info("Waiting for login completion (up to 5 minutes)...")
                start_time = time.time()
                login_successful = False

                while time.time() - start_time < 300:
                    time.sleep(2)
                    try:
                        current_url = page.url.lower()
                    except Exception:
                        # Page was closed by user
                        break

                    cookies = context.cookies()
                    has_li_at = any(c.get("name") == "li_at" and c.get("value") for c in cookies)

                    # Check if user navigated to logged-in pages and not in auth/challenge flow
                    is_on_logged_page = any(x in current_url for x in ["/feed", "/in/", "recent-activity", "/mynetwork", "/messaging"])
                    is_in_challenge = any(x in current_url for x in ["/checkpoint", "/login", "/signup", "/challenge", "/uas/"])

                    if has_li_at and is_on_logged_page and not is_in_challenge:
                        logger.info("Detected successful login and active session!")
                        page.wait_for_timeout(3000)
                        login_successful = True
                        break

                if login_successful or any(c.get("name") == "li_at" for c in context.cookies()):
                    # Save storage state
                    context.storage_state(path=str(self.session_file))
                    logger.info(f"Session saved successfully to {self.session_file}!")
                    print(f"\n✅ Oturum başarıyla kaydedildi: {self.session_file}\n")
                    browser.close()
                    return True
                else:
                    logger.error("Login timeout or browser closed without login.")
                    browser.close()
                    return False

            except Exception as e:
                logger.error(f"Error during interactive login: {e}")
                try:
                    browser.close()
                except Exception:
                    pass
                return False

    def scrape_latest_post(self) -> Optional[Dict[str, Any]]:
        """
        Scrapes the latest post from the configured LinkedIn activity page.
        Returns parsed post dictionary or None if scraping fails.
        """
        logger.info(f"Visiting LinkedIn activity page: {self.activity_url}")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ]
            )

            context = self._get_stealth_context(browser)
            page = context.new_page()
            page.set_default_timeout(config.page_timeout_ms)

            try:
                # Navigate to the activity page
                response = page.goto(
                    self.activity_url,
                    wait_until="domcontentloaded",
                    timeout=config.page_timeout_ms
                )

                # Human-like delay and scroll
                time.sleep(random.uniform(2.5, 4.0))

                # Check if redirected to authwall / login / signup
                current_url = page.url
                auth_keywords = ["authwall", "login", "checkpoint", "signup", "join", "uas"]
                if any(k in current_url.lower() for k in auth_keywords):
                    logger.warning(
                        f"LinkedIn oturum/giriş duvarına yönlendirdi: {current_url}\n"
                        "💡 Çözüm: Lütfen 'python main.py --login' komutunu çalıştırarak tarayıcıda 1 kez giriş yapın veya .env dosyasına LINKEDIN_LI_AT çerezinizi ekleyin."
                    )
                    self._save_debug_artifacts(page)
                    browser.close()
                    return None

                # Scroll down slightly to ensure dynamic feed is loaded
                page.evaluate("window.scrollBy(0, 500);")
                time.sleep(random.uniform(1.5, 2.5))

                # Candidate selectors for post cards
                post_card_selectors = [
                    ".feed-shared-update-v2",
                    "div[data-urn*='activity']",
                    "div[data-id*='activity']",
                    "div.profile-creator-shared-feed-update__container",
                    ".scaffold-finite-scroll__content > div",
                    "div.feed-shared-update-v2__content",
                    "li.profile-creator-shared-feed-update__container",
                ]

                post_element = None
                for selector in post_card_selectors:
                    elements = page.query_selector_all(selector)
                    for el in elements:
                        # Make sure element has text or substantial content
                        text = el.inner_text().strip()
                        if len(text) > 20:
                            post_element = el
                            logger.info(f"Found post card matching selector: {selector}")
                            break
                    if post_element:
                        break

                if not post_element:
                    logger.error("Could not locate any post elements on the activity page.")
                    self._save_debug_artifacts(page)
                    browser.close()
                    return None

                # Try to expand "...see more" button if present inside the post
                see_more_selectors = [
                    "button.feed-shared-inline-show-more-text__see-more-less-toggle",
                    "button[aria-label*='more']",
                    "button[aria-label*='fazla']",
                    "button:has-text('see more')",
                    "button:has-text('daha fazla')",
                ]
                for btn_sel in see_more_selectors:
                    try:
                        btn = post_element.query_selector(btn_sel)
                        if btn and btn.is_visible():
                            btn.click(timeout=2000)
                            time.sleep(0.5)
                            break
                    except Exception:
                        pass

                # Extract Text Content
                content_selectors = [
                    ".feed-shared-update-v2__description",
                    ".update-components-text",
                    ".feed-shared-text",
                    ".feed-shared-inline-show-more-text",
                    "span.break-words",
                ]

                raw_content = ""
                for c_sel in content_selectors:
                    c_el = post_element.query_selector(c_sel)
                    if c_el:
                        text = c_el.inner_text().strip()
                        if text:
                            raw_content = text
                            break

                if not raw_content:
                    # Fallback to general post element inner text
                    raw_content = post_element.inner_text()

                # Extract URN / URL
                urn = post_element.get_attribute("data-urn") or post_element.get_attribute("data-id") or ""
                
                raw_url = ""
                # Search for direct link inside post
                link_selectors = [
                    "a[href*='/feed/update/urn:li:activity:']",
                    "a[href*='/feed/update/']",
                    "a[href*='linkedin.com/posts/']",
                    "a.feed-shared-update-v2__sub-link",
                    "a.app-aware-link[href*='activity']",
                ]
                for l_sel in link_selectors:
                    link_el = post_element.query_selector(l_sel)
                    if link_el:
                        href = link_el.get_attribute("href")
                        if href:
                            raw_url = href
                            break

                # Extract Date / Time
                raw_date = ""
                date_selectors = [
                    "time",
                    ".update-components-actor__sub-description",
                    ".feed-shared-actor__sub-description",
                    "span.visually-hidden",
                ]
                for d_sel in date_selectors:
                    date_el = post_element.query_selector(d_sel)
                    if date_el:
                        dt_text = date_el.inner_text().strip()
                        # Often contains "1w • Edited • " - grab the first part
                        if dt_text:
                            raw_date = dt_text.split("•")[0].strip()
                            break

                # Parse into standard payload
                parsed_post = PostExtractor.parse_post(
                    raw_content=raw_content,
                    raw_url=raw_url,
                    raw_date=raw_date,
                    urn=urn,
                )

                browser.close()
                return parsed_post

            except Exception as e:
                logger.error(f"Unexpected error during LinkedIn scraping: {e}")
                self._save_debug_artifacts(page)
                browser.close()
                return None

    def _save_debug_artifacts(self, page: Page) -> None:
        """Saves screenshot and HTML dump for debugging scrape failures."""
        try:
            config.data_dir.mkdir(parents=True, exist_ok=True)
            screenshot_path = config.data_dir / "debug_screenshot.png"
            html_path = config.data_dir / "debug_page.html"

            page.screenshot(path=str(screenshot_path), full_page=True)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(page.content())

            logger.info(f"Saved debug artifacts: {screenshot_path} and {html_path}")
        except Exception as err:
            logger.warning(f"Could not save debug artifacts: {err}")
