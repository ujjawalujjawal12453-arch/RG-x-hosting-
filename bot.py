import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

import config
import database as db
from handlers import user as user_h
from handlers import admin as admin_h
import jobs

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
log = logging.getLogger("hosting-bot")


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # admin's multi-step "generate key" flow gets first shot
    handled = await admin_h.admin_text_handler(update, context)
    if handled:
        return
    await user_h.text_message_handler(update, context)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Catches things like TimedOut on flaky mobile networks so one bad
    request doesn't spam a full traceback / go unhandled."""
    err = context.error
    log.warning(f"Update caused error: {err}")
    # if it was a button tap, try to at least clear the 'loading' spinner on it
    if isinstance(update, Update) and update.callback_query:
        try:
            await update.callback_query.answer()
        except Exception:
            pass


def build_app():
    db.init_db()
    app = (
        ApplicationBuilder()
        .token(config.BOT_TOKEN)
        .concurrent_updates(256)   # handle many users' messages/uploads in parallel, not one-by-one
        .connection_pool_size(256)
        .pool_timeout(30)
        .connect_timeout(20)       # flaky mobile networks (e.g. Termux) need more slack than the 5s default
        .read_timeout(20)
        .write_timeout(20)
        .get_updates_read_timeout(30)
        .build()
    )
    app.add_error_handler(error_handler)

    app.add_handler(CommandHandler("start", user_h.start_cmd))
    app.add_handler(CommandHandler("whoami", user_h.whoami_cmd))

    # user menu buttons
    app.add_handler(CallbackQueryHandler(
        user_h.menu_callback,
        pattern="^menu_(activate|myhosting|buy|pricing|referral|trial|help|back)$",
    ))
    # admin menu buttons (incl. category picker + quick-gen from screenshot)
    app.add_handler(CallbackQueryHandler(
        admin_h.admin_menu_callback,
        pattern="^(menu_admin|admin_.*|gencat_.*|gentier_.*|quickgen_.*|unban_.*)$",
    ))
    # approve / reject
    app.add_handler(CallbackQueryHandler(
        admin_h.approval_callback,
        pattern="^(approve|reject)_\\d+$",
    ))
    app.add_handler(CallbackQueryHandler(
        admin_h.waitlist_callback,
        pattern="^waitlist_\\d+$",
    ))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    app.add_handler(MessageHandler(filters.Document.ALL, user_h.document_handler))
    app.add_handler(MessageHandler(filters.PHOTO, user_h.photo_handler))

    jq = app.job_queue
    jq.run_repeating(jobs.check_expired_hostings, interval=config.EXPIRY_CHECK_INTERVAL, first=10)
    jq.run_repeating(jobs.check_renewal_reminders, interval=3600, first=30)

    return app


if __name__ == "__main__":
    application = build_app()
    log.info("Bot starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)
