"""
Python script to automate train ticket availability checking on IRCTC website using Selenium,
with Telegram bot integration for scheduling control and notifications.

Requirements:
- selenium
- python-telegram-bot
- schedule

Usage:
- Configure TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.
- Run the script and use Telegram bot commands to start/stop checks.

"""

import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from telegram import Update, Bot
from telegram.ext import Updater, CommandHandler, CallbackContext
import threading
import schedule

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Telegram bot token and chat ID from environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
    logger.error("Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.")
    exit(1)

bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Global scheduler job
job = None

def check_ticket_availability(departure: str, destination: str, date: str) -> str:
    """
    Automate IRCTC train search and return availability info as string.
    """
    logger.info(f"Checking tickets from {departure} to {destination} on {date}")

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")

    driver = webdriver.Chrome(options=options)
    driver.get("https://www.irctc.co.in/nget/train-search")

    wait = WebDriverWait(driver, 20)

    try:
        # Close any popups if present
        try:
            wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Close']"))).click()
        except:
            pass

        # Input departure city
        from_input = wait.until(EC.element_to_be_clickable((By.ID, "origin")))
        from_input.clear()
        from_input.send_keys(departure)
        time.sleep(1)
        from_input.send_keys("\n")

        # Input destination city
        to_input = wait.until(EC.element_to_be_clickable((By.ID, "destination")))
        to_input.clear()
        to_input.send_keys(destination)
        time.sleep(1)
        to_input.send_keys("\n")

        # Input date
        date_input = wait.until(EC.element_to_be_clickable((By.ID, "jDate")))
        date_input.clear()
        date_input.send_keys(date)
        time.sleep(1)

        # Click search button
        search_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.search_btn")))
        search_button.click()

        # Wait for results to load
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.train_avl_enq_box")))

        # Extract availability info
        trains = driver.find_elements(By.CSS_SELECTOR, "div.train_avl_enq_box")
        if not trains:
            return "No trains found for the given parameters."

        result_lines = []
        for train in trains:
            train_name = train.find_element(By.CSS_SELECTOR, "div.train_name").text
            availability = train.find_element(By.CSS_SELECTOR, "div.avl_enq_box").text
            result_lines.append(f"{train_name}: {availability}")

        return "\n".join(result_lines)

    except Exception as e:
        logger.error(f"Error during ticket check: {e}")
        return f"Error during ticket check: {e}"

    finally:
        driver.quit()

def start_check(update: Update, context: CallbackContext):
    """
    Start periodic ticket availability checks.
    Usage: /startcheck departure destination date interval_minutes
    """
    global job
    if job:
        update.message.reply_text("Ticket checking is already running.")
        return

    try:
        departure = context.args[0]
        destination = context.args[1]
        date = context.args[2]
        interval = int(context.args[3]) if len(context.args) > 3 else 60
    except (IndexError, ValueError):
        update.message.reply_text("Usage: /startcheck departure destination date interval_minutes(optional, default=60)")
        return

    def job_func():
        availability = check_ticket_availability(departure, destination, date)
        bot.send_message(chat_id=update.effective_chat.id, text=f"Ticket availability:\n{availability}")

    job = schedule.every(interval).minutes.do(job_func)
    update.message.reply_text(f"Started ticket checking every {interval} minutes for {departure} to {destination} on {date}.")

    def run_schedule():
        while True:
            schedule.run_pending()
            time.sleep(1)

    threading.Thread(target=run_schedule, daemon=True).start()

def stop_check(update: Update, context: CallbackContext):
    """
    Stop periodic ticket availability checks.
    """
    global job
    if job:
        schedule.cancel_job(job)
        job = None
        update.message.reply_text("Stopped ticket checking.")
    else:
        update.message.reply_text("Ticket checking is not running.")

def main():
    updater = Updater(token=TELEGRAM_BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("startcheck", start_check))
    dispatcher.add_handler(CommandHandler("stopcheck", stop_check))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
