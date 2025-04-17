from playwright.sync_api import sync_playwright
import json
import re
import time
from datetime import datetime, timedelta
from collections import defaultdict
import sys
import requests
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler("steam_remover.log")]
)
logger = logging.getLogger("steam_remover")

# At the top of your script, add these variables
CONTINUOUS_OPERATION = True  # Set to True to keep scanning even when no packages are found
SCAN_INTERVAL = 600  # Time in seconds (10 minutes) between scans when no packages are found
last_empty_notification_time = None  # Track when we last sent "no packages" notification

class TelegramNotifier:
    def __init__(self):
        # Hardcoded Telegram bot credentials - replace with your own values
        self.telegram_token = "add-me"
        self.chat_id = "add-me"
        self.sent_notifications = set()
        self.last_connection_time = datetime.now()
        self.connection_notification_sent = False
        self.daily_summary_last_sent = None
        self.start_time = datetime.now()
        self.packages_removed_today = 0
        self.notification_cooldown = 24 * 60 * 60  # 24 hours in seconds
        self.notification_timestamps = {}
        
    def send_message(self, message):
        """Send message to Telegram chat"""
        if not self.telegram_token or self.telegram_token == "YOUR_TELEGRAM_BOT_TOKEN":
            logger.warning("Telegram token not configured. Skipping notification.")
            return False
            
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML"
            }
            response = requests.post(url, data=data)
            if response.status_code == 200:
                logger.info(f"Telegram notification sent: {message[:50]}...")
                return True
            else:
                logger.error(f"Failed to send Telegram notification: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}")
            return False
    
    def startup_notification(self):
        """Send startup notification"""
        message = "🎮 Steam Game Remover has started!\n⏱️ Script is now running."
        self.send_message(message)
    
    def send_error_notification(self, error_type, details):
        """Send error notification (max once per day per error type)"""
        now = datetime.now()
        last_sent = self.notification_timestamps.get(error_type)
        
        # Check if we've sent this notification in the last 24 hours
        if last_sent and (now - last_sent).total_seconds() < self.notification_cooldown:
            return
            
        message = f"⚠️ Error Alert: {error_type}\n{details}"
        if self.send_message(message):
            self.notification_timestamps[error_type] = now
    
    def check_connection_status(self):
        """Check if there's been no activity for 30 minutes"""
        if self.connection_notification_sent:
            return
            
        time_since_last_connection = (datetime.now() - self.last_connection_time).total_seconds()
        if time_since_last_connection > 30 * 60:  # 30 minutes
            message = "⚠️ Connection Alert: No activity detected for 30+ minutes."
            if self.send_message(message):
                self.connection_notification_sent = True
    
    def update_connection_time(self):
        """Update the last connection time"""
        self.last_connection_time = datetime.now()
        self.connection_notification_sent = False
    
    def check_daily_summary(self, removed_packages_count):
        """Send daily summary at 18:00"""
        now = datetime.now()
        today = now.date()
        
        # Check if we already sent a summary today
        if self.daily_summary_last_sent and self.daily_summary_last_sent.date() == today:
            return
            
        # Check if it's after 18:00
        if now.hour >= 18:
            uptime = now - self.start_time
            days, remainder = divider_mod(uptime.total_seconds(), 86400)
            hours, remainder = divider_mod(remainder, 3600)
            minutes, seconds = divider_mod(remainder, 60)
            
            message = (
                f"📊 Daily Summary Report\n"
                f"🕒 Script uptime: {int(days)}d {int(hours)}h {int(minutes)}m\n"
                f"🎮 Packages removed today: {self.packages_removed_today}\n"
                f"🗑️ Total packages removed: {removed_packages_count}"
            )
            
            if self.send_message(message):
                self.daily_summary_last_sent = now
                self.packages_removed_today = 0
    
    def record_package_removal(self):
        """Record that a package was removed"""
        self.packages_removed_today += 1
        self.update_connection_time()

def divider_mod(a, b):
    """Helper function to divide and get remainder"""
    return a // b, a % b

class PackageManager:
    def __init__(self):
        self.attempt_history = defaultdict(list)
        self.last_success_time = None
        self.last_attempt_time = None
        self.removed_packages = set()
        self.last_error_time = None
        
    def record_attempt(self, package_id, success):
        now = datetime.now()
        self.attempt_history[package_id].append((now, success))
        self.last_attempt_time = now
        
        if success:
            self.last_success_time = now
            self.removed_packages.add(package_id)
        else:
            self.last_error_time = now
    
    def get_next_package(self, available_packages):
        # Filter out removed packages
        available_packages = [p for p in available_packages if p not in self.removed_packages]
        
        # First, try packages that have never been attempted
        never_attempted = [p for p in available_packages if p not in self.attempt_history]
        if never_attempted:
            return never_attempted[0]
        
        # Then, find the package with the oldest last attempt
        oldest_attempt = float('inf')
        chosen_package = None
        
        for package in available_packages:
            if not self.attempt_history[package]:
                continue
            last_attempt = self.attempt_history[package][-1][0]
            if last_attempt.timestamp() < oldest_attempt:
                oldest_attempt = last_attempt.timestamp()
                chosen_package = package
        
        return chosen_package or available_packages[0] if available_packages else None

def check_cookies(page):
    """Check if cookies are valid by loading the licenses page."""
    try:
        response = page.goto("https://store.steampowered.com/account/licenses/", timeout=20000)
        if response.status == 200 and "javascript:RemoveFreeLicense" in page.content():
            print("✅ Cookies are valid!")
            return True
        else:
            print(f"❌ Cookies invalid: Status {response.status}")
            return False
    except Exception as e:
        print(f"❌ Error during cookie check: {e}")
        return False

def attempt_removal(page, session_id, package_id):
    """Attempt to remove a package with better error handling"""
    try:
        js_code = f"""
            (async () => {{
                try {{
                    const response = await fetch('https://store.steampowered.com/account/removelicense', {{
                        method: 'POST',
                        headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
                        body: `sessionid={session_id}&packageid={package_id}`
                    }});
                    
                    // Check if response is JSON
                    const contentType = response.headers.get('content-type');
                    if (!contentType || !contentType.includes('application/json')) {{
                        return {{ 
                            success: 0, 
                            error: 'Invalid response type: ' + contentType,
                            status: response.status
                        }};
                    }}
                    
                    const result = await response.json();
                    return result;
                }} catch (error) {{
                    return {{ 
                        success: 0, 
                        error: error.toString(),
                        status: 0
                    }};
                }}
            }})();
        """
        result = page.evaluate(js_code)
        
        # Check for various error conditions
        if not isinstance(result, dict):
            return {'success': 0, 'error': 'Invalid response format'}
        
        if result.get('status') == 401:
            print("⚠️ Session expired, need to refresh cookies")
            return {'success': 0, 'error': 'Session expired'}
            
        return result
    except Exception as e:
        return {'success': 0, 'error': str(e)}

def create_browser_session():
    """Create a new browser session with fresh context"""
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 720}
    )
    page = context.new_page()
    return browser, context, page

# Initialize package manager
pkg_manager = PackageManager()
# Initialize telegram notifier
telegram = TelegramNotifier()

# Start Playwright
with sync_playwright() as p:
    browser = None
    context = None
    page = None
    session_retries = 0
    MAX_SESSION_RETRIES = 3
    
    # Send startup notification
    telegram.startup_notification()

    while True:
        try:
            # Create new browser session if needed
            if not browser or not context or not page:
                if browser:
                    browser.close()
                browser, context, page = create_browser_session()
                logger.info("🌐 Created new browser session")

                # Load cookies from file
                try:
                    with open("cookies.json", "r") as f:
                        cookies = json.load(f)
                    context.add_cookies(cookies)
                    logger.info("🍪 Cookies successfully loaded from cookies.json")
                except FileNotFoundError:
                    error_msg = "⚠️ No cookies.json found. Please provide valid cookies file."
                    logger.error(error_msg)
                    telegram.send_error_notification("Missing Cookies", error_msg)
                    sys.exit(1)

            # Check cookie validity
            if not check_cookies(page):
                session_retries += 1
                if session_retries >= MAX_SESSION_RETRIES:
                    error_msg = "❌ Maximum session retry attempts reached. Please provide fresh cookies."
                    logger.error(error_msg)
                    telegram.send_error_notification("Cookie Failure", error_msg)
                    sys.exit(1)
                error_msg = f"❌ Invalid cookies detected. Retry attempt {session_retries}/{MAX_SESSION_RETRIES}"
                logger.error(error_msg)
                telegram.send_error_notification("Invalid Cookies", error_msg)
                logger.info("⏳ Waiting 2 minutes before retrying...")
                time.sleep(120)
                browser, context, page = create_browser_session()
                continue

            # Reset session retries on successful cookie check
            session_retries = 0
            telegram.update_connection_time()

            logger.info("\n🔍 Checking for licenses to remove...")
            page.goto("https://store.steampowered.com/account/licenses/", timeout=60000)
            html_content = page.content()
            package_ids = re.findall(r'javascript:RemoveFreeLicense\( (\d+),', html_content)
            package_count = len(package_ids)
            
            if package_count == 0:
                # Double-check by reloading once
                logger.info("🔍 Double-checking that no licenses remain...")
                time.sleep(2)
                page.reload()
                time.sleep(3)
                html_content = page.content()
                package_ids = re.findall(r'javascript:RemoveFreeLicense\( (\d+),', html_content)
                package_count = len(package_ids)
                
                if package_count == 0:
                    now = datetime.now()
                    # Only notify once per day about no packages
                    if last_empty_notification_time is None or (now - last_empty_notification_time).total_seconds() > 24*60*60:
                        logger.info("✅ No more licenses to remove!")
                        telegram.send_message("✅ No more licenses to remove. Will continue checking periodically.")
                        last_empty_notification_time = now
                    else:
                        logger.info("✅ No licenses found - continuing periodic scanning")
                    
                    if CONTINUOUS_OPERATION:
                        logger.info(f"⏳ Waiting {SCAN_INTERVAL} seconds before next scan...")
                        time.sleep(SCAN_INTERVAL)
                        continue  # Skip to next iteration rather than breaking
                    else:
                        break  # Exit if not in continuous mode

            logger.info(f"📦 Found {package_count} remaining packages")
            logger.info(f"🎯 Successfully removed {len(pkg_manager.removed_packages)} packages so far")

            # Get session ID from cookies
            cookies = context.cookies()
            session_id = next((cookie['value'] for cookie in cookies if cookie['name'] == 'sessionid'), None)
            if not session_id:
                logger.error("❌ Session ID not found in cookies. Restarting session...")
                browser, context, page = create_browser_session()
                continue

            # Get next package to try
            next_package = pkg_manager.get_next_package(package_ids)
            if not next_package:
                logger.warning("⚠️ No suitable package found for removal")
                time.sleep(60)
                continue

            logger.info(f"🎯 Attempting to remove package {next_package}")
            
            # Attempt removal with better error handling
            result = attempt_removal(page, session_id, next_package)
            
            if result.get('success') == 1:
                logger.info(f"✅ Successfully removed package {next_package}")
                pkg_manager.record_attempt(next_package, True)
                telegram.record_package_removal()
                
                # Wait 5-10 seconds after success
                wait_time = 5 + (5 * (datetime.now().microsecond % 100) / 100)
                logger.info(f"🔄 Success! Waiting {wait_time:.1f} seconds before next removal...")
                time.sleep(wait_time)
            else:
                # For any failure
                error_msg = result.get('error', 'Unknown error')
                logger.info(f"❌ Failed to remove package {next_package}: {error_msg}")
                
                # Handle session expiration
                if 'Session expired' in error_msg or 'Invalid response type' in error_msg:
                    logger.info("🔄 Session issues detected, restarting browser session...")
                    browser, context, page = create_browser_session()
                    continue
                
                pkg_manager.record_attempt(next_package, False)
                
                # Always use 600 seconds wait time for any error
                wait_time = 600
                logger.info(f"⏳ Error detected! Waiting {wait_time} seconds before next attempt...")
                time.sleep(wait_time)
            
            # Check for daily summary time
            telegram.check_daily_summary(len(pkg_manager.removed_packages))
            
            # Check for connection issues
            telegram.check_connection_status()

        except Exception as e:
            error_msg = f"❌ Error during execution: {e}"
            logger.error(error_msg)
            telegram.send_error_notification("Execution Error", error_msg)
            logger.info("⏳ Waiting 5 minutes before retrying...")
            time.sleep(300)
            # Restart browser session on error
            if browser:
                browser.close()
            browser = None

    if browser:
        browser.close()

    # Send final summary before exit
    if not CONTINUOUS_OPERATION:
        # Only send final summary if we're actually exiting
        final_message = f"🏁 Steam Game Remover completed\n🗑️ Total packages removed: {len(pkg_manager.removed_packages)}"
        telegram.send_message(final_message)
