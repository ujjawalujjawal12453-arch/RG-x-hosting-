import os
import logging
import zipfile
from telegram import Update
from telegram.ext import ContextTypes

import config
import database as db
import keyboards as kb
import ui_utils as ui
import scanner
import rules

log = logging.getLogger("hosting-bot")

STATE_WAIT_KEY = "wait_key"
STATE_WAIT_FILE = "wait_file"


def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


async def blocked_if_banned(update: Update, user) -> bool:
    """Returns True (and replies) if this user is banned — caller should stop."""
    if db.is_banned(user.id):
        await update.message.reply_text(
            "⛔ Aapko rules todne ki wajah se bot se ban kar diya gaya hai.\n"
            "Agar lagta hai ye galti hai to admin se seedha contact karo."
        )
        return True
    return False


async def notify_admin(context: ContextTypes.DEFAULT_TYPE, **kwargs):
    """Wraps send_message to admin so a failure is LOGGED instead of silently
    swallowed. #1 cause of 'admin didn't get notified': the admin never
    pressed /start on this bot — Telegram blocks bots from messaging a user
    who hasn't opened a chat with them first."""
    try:
        return await context.bot.send_message(chat_id=config.ADMIN_ID, **kwargs)
    except Exception as e:
        log.error(f"FAILED to notify admin ({config.ADMIN_ID}): {e}. "
                  f"Make sure the admin has pressed /start on this bot at least once.")
        return None


async def whoami_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    admin_tag = "\n\n✅ Tum ADMIN ho (config.py ka ADMIN_ID match karta hai)" if is_admin(user.id) else (
        f"\n\n⚠️ Tum admin NAHI ho. Configured ADMIN_ID: `{config.ADMIN_ID}`"
    )
    await update.message.reply_text(
        f"🙋 Name: {user.full_name}\n"
        f"👤 Username: @{user.username or 'no_username'}\n"
        f"🆔 Your ID: `{user.id}`"
        f"{admin_tag}",
        parse_mode="Markdown",
    )


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username or "")

    if await blocked_if_banned(update, user):
        return

    # referral deep-link: t.me/<bot>?start=ref<referrer_id>
    if context.args:
        arg = context.args[0]
        if arg.startswith("ref"):
            try:
                referrer_id = int(arg[3:])
                db.record_referral(referrer_id, user.id)
            except (ValueError, IndexError):
                pass

    if db.get_setting("bot_enabled", "1") != "1" and not is_admin(user.id):
        await update.message.reply_text(
            "🛑 Hosting service abhi maintenance mode mein hai. Thodi der baad try karein."
        )
        return

    text = (
        f"👋 *Swagat hai, {user.first_name}!* 🔥\n\n"
        "🖥️ *UM MODE OFF Hosting* — apna Bot 🤖 / API 🔌 / Website 🌐 yahan real mein host karwao.\n\n"
        "🔑 Pehle apni *key activate* karo (admin se milegi)\n"
        "📁 Fir apni file bhejo — admin approve karega ✅\n"
        "🚀 Approve hote hi tumhara hosting 24x7 live ho jayega\n\n"
        "👇 Neeche se option chuno"
    )
    if os.path.exists(config.LOGO_IMAGE_PATH):
        await update.message.reply_photo(
            photo=open(config.LOGO_IMAGE_PATH, "rb"),
            caption=text,
            parse_mode="Markdown",
            reply_markup=kb.main_menu(is_admin(user.id)),
        )
    else:
        await update.message.reply_text(
            text, parse_mode="Markdown", reply_markup=kb.main_menu(is_admin(user.id))
        )


async def menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id

    if db.is_banned(user_id):
        await query.answer("⛔ Aap banned ho.", show_alert=True)
        return

    if query.data == "menu_back":
        await ui.edit_menu(
            query, "🏠 *Main Menu*", reply_markup=kb.main_menu(is_admin(user_id))
        )
        return

    if query.data == "menu_activate":
        context.user_data["state"] = STATE_WAIT_KEY
        await ui.edit_menu(query, "🔑 Apni *8-digit key* bhejo:", reply_markup=kb.back_button())
        return

    if query.data == "menu_myhosting":
        await show_my_hosting(query, user_id)
        return

    if query.data == "menu_buy":
        await send_buy_info(update, context)
        return

    if query.data == "menu_trial":
        await handle_trial_claim(query, context)
        return

    if query.data == "menu_pricing":
        await show_pricing(query)
        return

    if query.data == "menu_referral":
        bot_username = (await context.bot.get_me()).username
        link = f"https://t.me/{bot_username}?start=ref{user_id}"
        bonus = db.get_bonus_days(user_id)
        await ui.edit_menu(
            query,
            f"👥 *Refer & Earn*\n\n"
            f"Apna link dosto ko bhejo — jab wo pehli baar key activate karenge:\n"
            f"🎁 Tumhe +{config.REFERRAL_BONUS_DAYS_REFERRER} free din milenge\n"
            f"🎁 Unhe +{config.REFERRAL_BONUS_DAYS_REFERRED} free din milenge\n\n"
            f"🔗 `{link}`\n\n"
            f"💰 Abhi tumhare paas *{bonus} banked free din* hain — agli key generate hote hi automatically add ho jayenge.",
            reply_markup=kb.back_button(),
        )
        return

    if query.data == "menu_help":
        await ui.edit_menu(
            query,
            "ℹ️ *Kaise use karein*\n\n"
            "1️⃣ 💰 Pricing dekho, 💳 Buy Key se QR se payment karo\n"
            "2️⃣ Screenshot admin ko bhejo — admin verify karega\n"
            "3️⃣ Admin key generate karega (Bot/API/Website + din)\n"
            "4️⃣ 🔑 Activate Key se apni key daalo\n"
            "5️⃣ Apni file bhejo (type ke hisab se) — admin approve karega\n"
            "6️⃣ ✅ Approve hote hi 24x7 live ho jayega\n\n"
            "⚠️ Har key ek hi baar use hoti hai, sirf usी username ke liye jiske naam par bani hai.",
            reply_markup=kb.back_button(),
        )
        return


async def show_pricing(query):
    lines = ["💰 *Pricing (per day)*\n"]
    for cat, info in config.HOSTING_TYPES.items():
        lines.append(f"{info['label']} — ₹{info['rate_per_day']}/din")
    lines.append("\nPrice = din × rate. Jitne din chahiye utna hi lagega.")
    lines.append("💳 Buy Key se payment karke le lo.")
    await ui.edit_menu(query, "\n".join(lines), reply_markup=kb.back_button())


async def send_buy_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    caption = (
        "💳 *Payment karo aur screenshot admin ko bhejo*\n\n"
        "Payment ke baad screenshot seedha admin ko bhejo. "
        "Verify hote hi tumhare username par key generate ho jayegi aur tumhe yahin mil jayegi.\n\n"
        "💰 Rate dekhne ke liye 💰 Pricing button use karo."
    )
    if os.path.exists(config.QR_IMAGE_PATH):
        await context.bot.send_photo(
            chat_id=query.from_user.id,
            photo=open(config.QR_IMAGE_PATH, "rb"),
            caption=caption,
            parse_mode="Markdown",
            reply_markup=kb.back_button(),
        )
        await query.delete_message()
    else:
        await ui.edit_menu(
            query, "⚠️ QR code abhi admin ne upload nahi kiya. Admin se seedha contact karo.",
            reply_markup=kb.back_button(),
        )


async def show_my_hosting(query, user_id):
    with_running = [h for h in db.running_hostings() if h["user_id"] == user_id]
    if not with_running:
        await ui.edit_menu(query, "📁 Abhi tumhara koi hosting live nahi hai.", reply_markup=kb.back_button())
        return
    lines = ["📁 *Tumhari Live Hosting:*\n"]
    for h in with_running:
        cat_label = config.HOSTING_TYPES.get(h["category"], {}).get("label", h["category"])
        port_txt = f" | Port: `{h['port']}`" if h["port"] else ""
        lines.append(
            f"• {cat_label} — `{h['filename']}`\n  Slot #{h['slot_number']}{port_txt} "
            f"⏳ Expires: {h['expires_at'][:16].replace('T',' ')}"
        )
    await ui.edit_menu(query, "\n\n".join(lines), reply_markup=kb.back_button())


async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get("state")
    if state == STATE_WAIT_KEY:
        await handle_key_input(update, context)


async def _register_wrong_attempt(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    n = context.user_data.get("wrong_key_attempts", 0) + 1
    context.user_data["wrong_key_attempts"] = n
    if n >= config.WRONG_KEY_ATTEMPT_LIMIT:
        context.user_data["wrong_key_attempts"] = 0
        await rules.strike(context, user, f"{n} galat key attempts (possible brute-force)")


async def handle_trial_claim(query, context: ContextTypes.DEFAULT_TYPE):
    user = query.from_user

    if not config.TRIAL_ENABLED:
        await ui.edit_menu(query, "🎁 Free trial abhi available nahi hai.", reply_markup=kb.back_button())
        return

    # everything below is checked against the database on the server —
    # nothing here trusts anything the client/button could fake
    if db.has_used_trial(user.id):
        await ui.edit_menu(
            query, "⚠️ Tumne pehle hi apna free trial use kar liya hai (sirf ek baar milta hai).",
            reply_markup=kb.back_button(),
        )
        return

    if db.running_trial_count() >= config.TRIAL_MAX_CONCURRENT:
        await ui.edit_menu(
            query, "😔 Abhi saari free trial slots busy hain — thodi der baad try karo.",
            reply_markup=kb.back_button(),
        )
        return

    if db.used_slots_count() >= config.MAX_SLOTS:
        await ui.edit_menu(
            query, "🛑 Server abhi full hai — free trial ke liye bhi slot nahi bacha.",
            reply_markup=kb.back_button(),
        )
        return

    if not user.username:
        await ui.edit_menu(
            query,
            "⚠️ Free trial ke liye Telegram username set hona zaroori hai. "
            "Settings mein username set karke phir try karo.",
            reply_markup=kb.back_button(),
        )
        return

    category = config.TRIAL_CATEGORY
    code = db.create_key(config.TRIAL_DAYS, 1, user.username, config.ADMIN_ID,
                          category=category, price=0, is_trial=1)
    db.activate_key(code, user.id)
    db.mark_trial_used(user.id)

    context.user_data["state"] = STATE_WAIT_FILE
    context.user_data["active_key"] = code

    cat_info = config.HOSTING_TYPES[category]
    exts = " ya ".join(cat_info["exts"])
    await ui.edit_menu(
        query,
        f"🎉 *Free Trial Activate Ho Gaya!*\n\n"
        f"{cat_info['label']} — {config.TRIAL_DAYS} din free\n\n"
        f"📁 Ab apni *{exts}* file bhejo — admin approve karte hi live ho jayega.",
        reply_markup=None,
    )
    await notify_admin(
        context,
        text=f"🎁 @{user.username} ne free trial claim kiya ({config.TRIAL_DAYS} din, {cat_info['label']}).",
    )



    ref = db.get_unrewarded_referral(user.id)
    if not ref:
        return
    db.mark_referral_rewarded(ref["id"])
    db.add_bonus_days(ref["referrer_id"], config.REFERRAL_BONUS_DAYS_REFERRER)
    db.add_bonus_days(user.id, config.REFERRAL_BONUS_DAYS_REFERRED)

    try:
        await context.bot.send_message(
            chat_id=ref["referrer_id"],
            text=(
                f"🎉 Tumhare refer kiye hue dost ne apni pehli key activate kar li!\n"
                f"🎁 Tumhe *{config.REFERRAL_BONUS_DAYS_REFERRER} free din* mile hain — "
                f"agli key generate hote hi automatically add ho jayenge."
            ),
            parse_mode="Markdown",
        )
    except Exception:
        pass

    await context.bot.send_message(
        chat_id=user.id,
        text=(
            f"🎁 Referral se aane ki wajah se tumhe *{config.REFERRAL_BONUS_DAYS_REFERRED} free din* mile hain — "
            f"agli key mein automatically add ho jayenge!"
        ),
        parse_mode="Markdown",
    )

    await notify_admin(
        context,
        text=(
            f"👥 *Referral Convert Hua!*\n\n"
            f"Referrer: `{ref['referrer_id']}` (+{config.REFERRAL_BONUS_DAYS_REFERRER} din)\n"
            f"Naya user: @{user.username or user.id} (+{config.REFERRAL_BONUS_DAYS_REFERRED} din)"
        ),
        parse_mode="Markdown",
    )


async def handle_key_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    user = update.effective_user
    context.user_data["state"] = None

    if await blocked_if_banned(update, user):
        return

    if not (code.isdigit() and len(code) == 8):
        await update.message.reply_text("❌ *Wrong format!* Key 8-digit number honi chahiye.",
                                         parse_mode="Markdown")
        return

    row = db.get_key(code)
    if not row:
        await _register_wrong_attempt(update, context, user)
        await update.message.reply_text("❌ *Wrong key!* Ye key exist nahi karti.", parse_mode="Markdown")
        return

    if row["status"] != "unused":
        await _register_wrong_attempt(update, context, user)
        await update.message.reply_text(
            "❌ *Wrong key!* Ye key already use ho chuki hai ya band kar di gayi hai.",
            parse_mode="Markdown",
        )
        return

    assigned = (row["assigned_username"] or "").lower()
    actual = (user.username or "").lower()
    if assigned and assigned != actual:
        await _register_wrong_attempt(update, context, user)
        await update.message.reply_text(
            "❌ *Wrong key!* Ye key tumhare liye nahi hai — kisi aur username ke liye bani hai.",
            parse_mode="Markdown",
        )
        return

    context.user_data["wrong_key_attempts"] = 0

    expires_at = db.activate_key(code, user.id)
    context.user_data["state"] = STATE_WAIT_FILE
    context.user_data["active_key"] = code

    await _reward_referral_if_any(context, user)

    cat = row["category"]
    cat_info = config.HOSTING_TYPES.get(cat, config.HOSTING_TYPES["bot"])
    exts = " ya ".join(cat_info["exts"])
    await update.message.reply_text(
        f"✅ *Key Sahi hai! Activated.*\n\n"
        f"{cat_info['label']}\n"
        f"⏳ Valid till: `{expires_at.strftime('%Y-%m-%d %H:%M')} UTC`\n\n"
        f"📁 Ab apni *{exts}* file bhejo — admin approve karte hi live ho jayega.",
        parse_mode="Markdown",
    )


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.upsert_user(user.id, user.username or "")
    if await blocked_if_banned(update, user):
        return

    active_key = context.user_data.get("active_key")

    if not active_key:
        await update.message.reply_text(
            "⚠️ Pehle apni key activate karo (🔑 Activate Key menu se), fir file bhejo."
        )
        return

    key_row = db.get_key(active_key)
    if not key_row or key_row["status"] != "active" or key_row["activated_by"] != user.id:
        await update.message.reply_text("⚠️ Tumhari key valid nahi hai. Pehle key activate karo.")
        return

    category = key_row["category"]
    cat_info = config.HOSTING_TYPES.get(category, config.HOSTING_TYPES["bot"])

    doc = update.message.document
    ext = os.path.splitext(doc.file_name)[1].lower()
    if ext not in cat_info["exts"]:
        allowed = " ya ".join(cat_info["exts"])
        await update.message.reply_text(
            f"❌ `{ext}` is {cat_info['label']} ke liye supported nahi hai. Sirf {allowed} bhejo.",
            parse_mode="Markdown",
        )
        return

    status_msg = await update.message.reply_text("📥 File receive ho rahi hai...")

    user_dir = os.path.join(config.USER_FILES_DIR, str(user.id), active_key)
    os.makedirs(user_dir, exist_ok=True)
    filepath = os.path.join(user_dir, doc.file_name)

    tg_file = await doc.get_file()
    await tg_file.download_to_drive(filepath)

    # website zips get extracted right away so the folder is ready to serve
    if category == "website" and ext == ".zip":
        extract_dir = os.path.join(user_dir, "site")
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(filepath, "r") as z:
            z.extractall(extract_dir)
        filepath = extract_dir  # process_manager serves this directory

    language = "python" if ext == ".py" else ("node" if ext == ".js" else "static")
    hosting_id = db.create_hosting_request(
        user.id, active_key, doc.file_name, filepath, language, category=category
    )

    scan_summary = scanner.scan_file(filepath)
    if "🚩 Flags found" in scan_summary:
        await rules.strike(context, user, f"Risky file uploaded: {doc.file_name}")

    await status_msg.edit_text(
        "✅ File mil gayi! Admin ke paas approval ke liye bhej di gayi hai.\n"
        "⏳ Approve hote hi tumhe message aayega."
    )

    sent = await notify_admin(
        context,
        text=(
            f"📥 *Naya Hosting Request*\n\n"
            f"{cat_info['label']}\n"
            f"👤 User: @{user.username or user.id} (`{user.id}`)\n"
            f"🔑 Key: `{active_key}`\n"
            f"📄 File: `{doc.file_name}`\n"
            f"🆔 Request ID: `{hosting_id}`\n\n"
            f"{scan_summary}"
        ),
        parse_mode="Markdown",
        reply_markup=kb.approval_buttons(hosting_id),
    )
    if sent is None:
        # tell the user honestly rather than leaving them thinking it's "in review" forever
        await update.message.reply_text(
            "⚠️ Request save ho gayi hai, lekin admin ko notify nahi kar paaye "
            "(shayad admin ne is bot par kabhi /start nahi dabaya). Seedha admin se contact karo."
        )


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Any photo sent to the bot is treated as a payment screenshot and
    forwarded to admin IMMEDIATELY with a one-tap 'Generate Key' shortcut.
    (Works even if the admin sends it to themself, e.g. while testing.)"""
    user = update.effective_user
    if await blocked_if_banned(update, user):
        return

    db.upsert_user(user.id, user.username or "")

    if rules.photo_is_spamming(user.id):
        banned_now = await rules.strike(context, user, "Bahut zyada screenshots bhej raha hai (spam)")
        if not banned_now:
            await update.message.reply_text(
                "⚠️ Bahut fast screenshots bhej rahe ho — thoda ruk kar bhejo."
            )
        return  # don't forward this one — this is exactly what protects admin's phone

    photo = update.message.photo[-1]  # highest resolution

    await update.message.reply_text("📤 Screenshot admin ko bhej diya gaya hai — thodi der mein verify hoga ✅")

    log.info(f"Forwarding payment screenshot from user_id={user.id} username={user.username} "
             f"to ADMIN_ID={config.ADMIN_ID}")

    try:
        sent = await context.bot.send_photo(
            chat_id=config.ADMIN_ID,
            photo=photo.file_id,
            caption=(
                f"💰 *Payment Screenshot Aaya!*\n\n"
                f"🙋 Name: {user.full_name}\n"
                f"👤 Username: @{user.username or 'no_username'}\n"
                f"🆔 ID: `{user.id}`\n\n"
                f"Verify karke neeche se seedha key generate kar do 👇"
            ),
            parse_mode="Markdown",
            reply_markup=kb.quickgen_button(user.id, user.username or ""),
        )
    except Exception as e:
        log.error(f"FAILED to forward payment screenshot to admin ({config.ADMIN_ID}): {e}. "
                  f"Check ADMIN_ID in .env is correct and that the admin has pressed /start.")
        sent = None

    if sent is None:
        await update.message.reply_text(
            "⚠️ Admin ko notify nahi kar paaye — seedha admin se message karke screenshot bhejo.\n"
            "(Agar tum khud admin ho: apna .env ka ADMIN_ID /whoami command se check karo)"
        )
