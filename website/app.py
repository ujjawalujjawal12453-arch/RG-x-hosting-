"""
UM MODE OFF — Free Trial claim website.

Runs as its OWN process (can be deployed on Render, separate from bot.py)
but reads/writes the SAME SQLite database, so everything stays in sync.

Flow (all server-side, nothing trusts the client):
  1. User enters Telegram ID -> server checks trial stock/eligibility
  2. If eligible: server creates a one-time token, builds a link-locker URL
     (GPLinks/Linkvertise/etc.) around /unlock/<token>
  3. User completes the locker's task -> gets redirected back to
     /unlock/<token> -> server marks that token task_done
  4. Server sends a PIN to that Telegram ID via DM (proves account ownership)
  5. User enters the PIN -> server re-checks EVERY rule one more time, and
     only then creates + activates a 16-digit trial key directly in the DB
  6. The key is delivered via Telegram DM ONLY — never shown on the website
"""
import os
import sys
import random
import string
import logging
from datetime import datetime, timedelta

import requests
from flask import Flask, render_template, request, jsonify, redirect

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))               # website/ itself (for linklocker)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # project root (for config, database)
import config
import database as db
import linklocker

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("trial-website")

app = Flask(__name__)
app.secret_key = config.WEB_SECRET_KEY

TG_API = f"https://api.telegram.org/bot{config.BOT_TOKEN}"


def tg_send_message(chat_id: int, text: str) -> bool:
    try:
        r = requests.post(
            f"{TG_API}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        return r.status_code == 200
    except Exception as e:
        log.error(f"Telegram send failed for {chat_id}: {e}")
        return False


def strike_and_maybe_ban(telegram_id: int, reason: str) -> bool:
    """Sync version of the bot's rules.strike() — this process has no async
    Telegram bot instance, just HTTP calls."""
    count = db.add_violation(telegram_id, reason)
    banned_now = False
    if count >= config.MAX_VIOLATIONS_BEFORE_BAN and not db.is_banned(telegram_id):
        db.ban_user(telegram_id, reason=f"{count} violations — last: {reason}")
        banned_now = True

    admin_text = (
        f"🚨 Rule Violation ({count}/{config.MAX_VIOLATIONS_BEFORE_BAN}) — via website\n"
        f"User ID: {telegram_id}\nReason: {reason}"
    )
    if banned_now:
        admin_text += "\n⛔ User AUTO-BANNED — repeated violations."
    tg_send_message(config.ADMIN_ID, admin_text)
    return banned_now


def _check_trial_eligibility(telegram_id: int):
    """Returns None if eligible, or an (http_code, error_message) tuple if not."""
    if not config.TRIAL_ENABLED:
        return 400, "Free trial abhi available nahi hai."
    if db.is_banned(telegram_id):
        return 403, "Ye account banned hai."
    user = db.find_user_by_id(telegram_id)
    if not user:
        return 404, ("Ye ID bot mein registered nahi hai. Pehle Telegram bot par /start karo, "
                      "fir /whoami se apni ID confirm karo.")
    if db.has_used_trial(telegram_id):
        return 400, "Tumne pehle hi free trial use kar liya hai."
    if db.running_trial_count() >= config.TRIAL_MAX_CONCURRENT:
        return 400, "Saari trial slots abhi busy hain — thodi der baad try karo."
    if db.used_slots_count() >= config.MAX_SLOTS:
        return 400, "Server full hai — trial ke liye bhi slot nahi bacha."
    if not (user["username"] or ""):
        return 400, "Telegram username set karo (Settings mein), fir try karo."
    return None


@app.route("/")
def index():
    return render_template("index.html", trial_days=config.TRIAL_DAYS)


@app.route("/api/start-trial", methods=["POST"])
def start_trial():
    data = request.get_json(silent=True) or {}
    raw_id = str(data.get("telegram_id", "")).strip()
    if not raw_id.isdigit():
        return jsonify({"ok": False, "error": "Telegram ID sirf number hona chahiye."}), 400
    telegram_id = int(raw_id)

    err = _check_trial_eligibility(telegram_id)
    if err:
        return jsonify({"ok": False, "error": err[1]}), err[0]

    token = db.create_trial_claim(telegram_id, config.TRIAL_TOKEN_EXPIRY_SECONDS)
    destination_url = f"{config.PUBLIC_BASE_URL}/unlock/{token}"
    locked_url = linklocker.create_locked_link(destination_url)

    return jsonify({
        "ok": True,
        "token": token,
        "locked_url": locked_url,
        "locker_active": config.LINKLOCKER_ENABLED,
    })


@app.route("/unlock/<token>")
def unlock(token):
    claim = db.get_trial_claim(token)
    if not claim:
        return render_template("message.html", title="Invalid Link",
                                text="Ye link valid nahi hai. Wapas jaake dobara try karo."), 404
    if datetime.utcnow().isoformat() > claim["expires_at"]:
        return render_template("message.html", title="Link Expired",
                                text="Ye link expire ho gaya. Wapas jaake dobara try karo."), 400
    if claim["status"] == "pending_task":
        db.mark_trial_claim_task_done(token)
    # bounce back to the main page with the token — it auto-advances to the PIN step
    return redirect(f"/?token={token}")


@app.route("/api/request-pin", methods=["POST"])
def request_pin():
    data = request.get_json(silent=True) or {}
    token = str(data.get("token", "")).strip()
    claim = db.get_trial_claim(token)
    if not claim:
        return jsonify({"ok": False, "error": "Invalid ya expired session. Dobara shuru karo."}), 400
    if claim["status"] not in ("task_done",):
        return jsonify({"ok": False, "error": "Pehle task complete karo."}), 400
    if datetime.utcnow().isoformat() > claim["expires_at"]:
        return jsonify({"ok": False, "error": "Session expire ho gaya. Dobara shuru karo."}), 400

    telegram_id = claim["telegram_id"]
    if db.is_banned(telegram_id):
        return jsonify({"ok": False, "error": "Ye account banned hai."}), 403

    pin = "".join(random.choices(string.digits, k=config.PIN_LENGTH))
    expires_at = (datetime.utcnow() + timedelta(seconds=config.PIN_EXPIRY_SECONDS)).isoformat()
    db.create_pin(telegram_id, pin, expires_at)

    sent = tg_send_message(
        telegram_id,
        f"🔐 *Free Trial Verification*\n\nTumhara PIN: `{pin}`\n\n"
        f"Ye {config.PIN_EXPIRY_SECONDS // 60} minute ke liye valid hai. Website par wapas jaake ye PIN daalo.",
    )
    if not sent:
        return jsonify({"ok": False, "error": "PIN bhej nahi paaye. Bot par /start kiya hai ya nahi check karo."}), 502

    return jsonify({"ok": True, "message": "PIN Telegram par bhej diya gaya hai."})


@app.route("/api/verify-pin", methods=["POST"])
def verify_pin():
    data = request.get_json(silent=True) or {}
    token = str(data.get("token", "")).strip()
    entered_pin = str(data.get("pin", "")).strip()

    claim = db.get_trial_claim(token)
    if not claim or claim["status"] != "task_done":
        return jsonify({"ok": False, "error": "Invalid ya expired session. Dobara shuru karo."}), 400

    telegram_id = claim["telegram_id"]
    if db.is_banned(telegram_id):
        return jsonify({"ok": False, "error": "Ye account banned hai."}), 403

    row = db.get_pin(telegram_id)
    if not row:
        return jsonify({"ok": False, "error": "Pehle PIN request karo."}), 400
    if datetime.utcnow().isoformat() > row["expires_at"]:
        db.clear_pin(telegram_id)
        return jsonify({"ok": False, "error": "PIN expire ho gaya. Dobara request karo."}), 400

    if entered_pin != row["pin"]:
        attempts = db.increment_pin_attempts(telegram_id)
        remaining = config.PIN_MAX_ATTEMPTS - attempts
        if attempts >= config.PIN_MAX_ATTEMPTS:
            db.clear_pin(telegram_id)
            banned_now = strike_and_maybe_ban(telegram_id, "Wrong PIN 3 baar (possible bypass attempt)")
            msg = ("⛔ Bahut galat attempts — account banned kar diya gaya hai." if banned_now else
                   "⚠️ Bahut galat attempts — ye ek violation strike ban gaya hai. Dobara shuru karo.")
            return jsonify({"ok": False, "error": msg}), 403
        return jsonify({"ok": False, "error": f"❌ Galat PIN. {remaining} attempt(s) bache hain."}), 400

    # PIN correct AND task was verified done — re-check every rule one last time
    db.clear_pin(telegram_id)
    err = _check_trial_eligibility(telegram_id)
    if err:
        return jsonify({"ok": False, "error": err[1]}), err[0]

    user = db.find_user_by_id(telegram_id)
    category = config.TRIAL_CATEGORY
    code = db.create_key(config.TRIAL_DAYS, 1, user["username"], config.ADMIN_ID,
                          category=category, price=0, is_trial=1, key_length=config.TRIAL_KEY_LENGTH)
    db.activate_key(code, telegram_id)
    db.mark_trial_used(telegram_id)
    db.mark_trial_claim_completed(token)

    cat_info = config.HOSTING_TYPES[category]
    tg_send_message(
        telegram_id,
        f"🎉 *Free Trial Verified & Activated!*\n\n"
        f"{cat_info['label']} — {config.TRIAL_DAYS} din free\n"
        f"🔑 Key: `{code}`\n\n"
        f"Bot mein wapas jaake apni file bhej do — admin approve karte hi live ho jayega. "
        f"(Key already activate ho chuki hai, dobara dalne ki zaroorat nahi.)",
    )
    tg_send_message(config.ADMIN_ID, f"🎁 @{user['username']} ne website (task-verified) se free trial claim kiya.")

    return jsonify({"ok": True, "message": "Verified! Tumhare Telegram par trial activate ho gaya hai — wahin file bhejo."})


if __name__ == "__main__":
    db.init_db()
    app.run(host=config.WEB_HOST, port=config.WEB_PORT, debug=False)
