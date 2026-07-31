from datetime import datetime
from telegram.ext import ContextTypes

import database as db
import process_manager as pm
import keyboards as kb
import config


async def check_expired_hostings(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.utcnow()
    for h in db.running_hostings():
        if not h["expires_at"]:
            continue
        expires_at = datetime.fromisoformat(h["expires_at"])
        if now >= expires_at:
            pm.stop_process(h["id"], h["pid"])
            db.stop_hosting(h["id"], reason_status="expired")
            db.ban_key(h["key_code"])  # single-use key, fully spent now
            try:
                await context.bot.send_message(
                    chat_id=h["user_id"],
                    text=(
                        f"⏳ Tumhari hosting ka time khatm ho gaya hai.\n"
                        f"📄 `{h['filename']}` ab band ho chuka hai.\n"
                        f"🔑 Naye key ke liye admin se contact karo."
                    ),
                    parse_mode="Markdown",
                )
            except Exception:
                pass
            try:
                await context.bot.send_message(
                    chat_id=config.ADMIN_ID,
                    text=f"♻️ Slot #{h['slot_number']} free ho gaya (hosting #{h['id']} expire ho gayi).",
                )
            except Exception:
                pass
            await _promote_next_waitlisted(context)
        elif h["pid"] and not pm.is_alive(h["pid"]):
            # process crashed / was killed outside our control
            db.stop_hosting(h["id"], reason_status="stopped")
            try:
                await context.bot.send_message(
                    chat_id=h["user_id"],
                    text=f"⚠️ Tumhara bot `{h['filename']}` crash ho gaya. Admin se contact karo.",
                    parse_mode="Markdown",
                )
            except Exception:
                pass


async def _promote_next_waitlisted(context: ContextTypes.DEFAULT_TYPE):
    """A slot just freed up — pull the OLDEST waitlisted request and give admin
    ONE clean approval prompt for it, instead of dumping the whole backlog."""
    nxt = db.next_waitlisted()
    if not nxt:
        return
    db.move_waitlisted_to_pending(nxt["id"])
    cat_info = config.HOSTING_TYPES.get(nxt["category"], {"label": nxt["category"]})
    try:
        await context.bot.send_message(
            chat_id=config.ADMIN_ID,
            text=(
                f"📋 *Waitlist se agla request ready hai!*\n\n"
                f"{cat_info['label']}\n"
                f"📄 File: `{nxt['filename']}`\n"
                f"🆔 Request ID: `{nxt['id']}`"
            ),
            parse_mode="Markdown",
            reply_markup=kb.approval_buttons(nxt["id"]),
        )
    except Exception:
        pass


async def check_renewal_reminders(context: ContextTypes.DEFAULT_TYPE):
    """Nudges users ~24h before their hosting expires so they renew in time
    instead of just losing access — straightforward extra revenue."""
    import keyboards as kb
    for h in db.hostings_expiring_soon(hours=24):
        cat_info = config.HOSTING_TYPES.get(h["category"], {"label": h["category"]})
        try:
            await context.bot.send_message(
                chat_id=h["user_id"],
                text=(
                    f"⏰ *Reminder:* tumhari {cat_info['label']} hosting `{h['filename']}` "
                    f"24 ghante mein expire ho jayegi.\n\n"
                    f"Band hone se bachane ke liye time se renew kar lo — 💳 Buy Key se naya key le lo."
                ),
                parse_mode="Markdown",
                reply_markup=kb.back_button(),
            )
        except Exception:
            pass
        db.mark_reminded(h["id"])
