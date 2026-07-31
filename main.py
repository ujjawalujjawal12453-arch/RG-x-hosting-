"""
Single entry point for Render (or any single-process host).

Render only runs ONE process per Web Service. This file starts the
Flask website (bound to Render's $PORT, so Render sees it as "up") in a
background thread, and runs the Telegram bot's polling loop in the main
thread — both inside the SAME process, so they always share the exact
same config.py / database.py / data/bot.db with zero chance of mismatch.

Render's start command (already set in Procfile) is simply:
    python3 main.py
"""
import logging
import threading

from telegram import Update

import config
import database as db
import bot as bot_module
from website.app import app as flask_app

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
log = logging.getLogger("main")


def _sanity_check_public_url():
    """The #1 cause of 'the trial link does nothing' is PUBLIC_BASE_URL still
    pointing at localhost after deploying somewhere real — warn loudly."""
    if "localhost" in config.PUBLIC_BASE_URL or "127.0.0.1" in config.PUBLIC_BASE_URL:
        log.warning(
            "⚠️  PUBLIC_BASE_URL abhi bhi '%s' hai. Agar ye Render (ya kisi aur "
            "server) par deploy ho raha hai, to isse apne asli public URL par "
            "set karo (.env / Render Environment tab mein), warna free-trial "
            "wala link kabhi kaam nahi karega — kisi ke phone/browser se "
            "'localhost' pahunchne wala nahi hai.",
            config.PUBLIC_BASE_URL,
        )
    else:
        log.info(f"PUBLIC_BASE_URL sahi lag raha hai: {config.PUBLIC_BASE_URL}")


def run_website():
    log.info(f"Website background thread mein start ho rahi hai — port {config.WEB_PORT}")
    flask_app.run(host=config.WEB_HOST, port=config.WEB_PORT, debug=False, use_reloader=False)


def main():
    db.init_db()
    _sanity_check_public_url()

    website_thread = threading.Thread(target=run_website, daemon=True)
    website_thread.start()

    log.info("Bot main thread mein start ho raha hai (polling)...")
    application = bot_module.build_app()
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
