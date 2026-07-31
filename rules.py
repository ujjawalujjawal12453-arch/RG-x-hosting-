"""
Rules & Regulations enforcement.

- Every violation (risky file upload flagged by the Quick-Scan, key
  brute-forcing, screenshot spam) adds a "strike".
- After config.MAX_VIOLATIONS_BEFORE_BAN strikes, the user is auto-banned
  and can no longer use the bot (checked in every handler).
- Admin is notified every time, and can unban from the Admin Panel.
"""
import time
import logging
from collections import defaultdict

import config
import database as db

log = logging.getLogger("hosting-bot")

# in-memory sliding-window counters for spam detection (per-process; resets on restart)
_photo_timestamps = defaultdict(list)


def photo_is_spamming(user_id: int) -> bool:
    now = time.time()
    window_start = now - config.PHOTO_SPAM_WINDOW_SECONDS
    hits = [t for t in _photo_timestamps[user_id] if t >= window_start]
    hits.append(now)
    _photo_timestamps[user_id] = hits
    return len(hits) > config.PHOTO_SPAM_LIMIT


async def strike(context, user, reason: str):
    """Adds a violation strike, bans on threshold, and always tells admin."""
    count = db.add_violation(user.id, reason)
    banned_now = False

    if count >= config.MAX_VIOLATIONS_BEFORE_BAN and not db.is_banned(user.id):
        db.ban_user(user.id, reason=f"{count} violations — last: {reason}")
        banned_now = True

    try:
        text = (
            f"🚨 *Rule Violation* ({count}/{config.MAX_VIOLATIONS_BEFORE_BAN})\n\n"
            f"👤 @{user.username or 'no_username'} (`{user.id}`)\n"
            f"📋 Reason: {reason}"
        )
        if banned_now:
            text += "\n\n⛔ *User AUTO-BANNED* — repeated violations."
        await context.bot.send_message(chat_id=config.ADMIN_ID, text=text, parse_mode="Markdown")
    except Exception as e:
        log.error(f"Failed to notify admin about violation: {e}")

    return banned_now
