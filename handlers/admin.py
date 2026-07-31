import asyncio
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes

import config
import database as db
import keyboards as kb
import process_manager as pm
import ui_utils as ui

GEN_DAYS, GEN_DEVICES, GEN_USERNAME = "gen_days", "gen_devices", "gen_username"
BROADCAST_WAIT = "broadcast_wait"


def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


async def spin(query, final_text_fn, frames=4, delay=0.35):
    """Small rotating-emoji loading animation before showing final content."""
    for i in range(frames):
        frame = kb.SPINNER_FRAMES[i % len(kb.SPINNER_FRAMES)]
        try:
            await ui.edit_menu(query, f"{frame} Loading...", reply_markup=None)
        except Exception:
            pass
        await asyncio.sleep(delay)
    text, markup = final_text_fn()
    await ui.edit_menu(query, text, reply_markup=markup)


async def admin_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.answer("Ye sirf admin ke liye hai.", show_alert=True)
        return
    await query.answer()

    if query.data == "menu_admin":
        enabled = db.get_setting("bot_enabled", "1") == "1"
        await ui.edit_menu(query, "⚙️ *Admin Panel*", reply_markup=kb.admin_menu(enabled))
        return

    if query.data == "admin_genkey":
        await ui.edit_menu(
            query,
            "🆕 *Key Generate Karo*\n\nPehle hosting type chuno 👇\n(Price auto-calculate hoga din x rate se)",
            reply_markup=kb.category_picker(),
        )
        return

    if query.data.startswith("gencat_"):
        category = query.data.split("_", 1)[1]
        context.user_data["gen_category"] = category
        cat_info = config.HOSTING_TYPES[category]
        await ui.edit_menu(
            query,
            f"{cat_info['label']} chuna ✅ (₹{cat_info['rate_per_day']}/din)\n\n"
            "Ab tier chuno 👇",
            reply_markup=kb.tier_picker(),
        )
        return

    if query.data.startswith("gentier_"):
        tier = query.data.split("_", 1)[1]  # standard / priority / vip
        context.user_data["gen_priority"] = 1 if tier in ("priority", "vip") else 0
        context.user_data["gen_vip"] = 1 if tier == "vip" else 0
        context.user_data["state"] = GEN_DAYS
        surcharge = 0
        if tier == "priority":
            surcharge = config.PRIORITY_SURCHARGE_PERCENT
        elif tier == "vip":
            surcharge = config.VIP_SURCHARGE_PERCENT
        tier_label = {"standard": "⚪ Standard", "priority": "⭐ Priority", "vip": "👑 VIP"}[tier]
        extra = f" (+{surcharge}% surcharge)" if surcharge else ""
        await ui.edit_menu(
            query,
            f"{tier_label} chuna ✅{extra}\n\n"
            "Kitne *din* ke liye key chahiye? (number bhejo, e.g. 30)",
            reply_markup=kb.back_button(),
        )
        return

    if query.data.startswith("quickgen_"):
        _, uid, uname = query.data.split("_", 2)
        context.user_data["gen_username_prefill"] = uname
        context.user_data["gen_target_id"] = int(uid)
        await query.message.reply_text(
            f"🆕 Key generate ho rahi hai @{uname or uid} ke liye.\n\nPehle hosting type chuno 👇",
            reply_markup=kb.category_picker(),
        )
        return

    if query.data == "admin_broadcast":
        context.user_data["state"] = BROADCAST_WAIT
        await ui.edit_menu(
            query,
            "📢 *Broadcast Message*\n\nJo message bhejna hai wo type karo — "
            "sabhi users ko ek saath chala jayega.",
            reply_markup=kb.back_button(),
        )
        return

    if query.data == "admin_banned":
        banned = db.banned_users()
        if not banned:
            await ui.edit_menu(query, "🚫 Koi bhi user banned nahi hai.", reply_markup=kb.back_button())
            return
        lines = ["🚫 *Banned Users*\n"]
        for r in banned:
            lines.append(f"• @{r['username'] or r['user_id']} (`{r['user_id']}`)\n  Reason: {r['ban_reason']}")
        await ui.edit_menu(query, "\n".join(lines), reply_markup=kb.unban_buttons(banned))
        return

    if query.data.startswith("unban_"):
        uid = int(query.data.split("_", 1)[1])
        db.unban_user(uid)
        await ui.edit_menu(query, f"✅ User `{uid}` unban ho gaya.", reply_markup=kb.back_button())
        try:
            await context.bot.send_message(chat_id=uid, text="✅ Aapko unban kar diya gaya hai. Ab bot use kar sakte ho.")
        except Exception:
            pass
        return

    if query.data == "admin_stats":
        def final():
            text = (
                "📊 *Aaj ka Business*\n\n"
                f"🔑 Keys generate hui: {db.keys_created_today()}\n"
                f"✅ Keys activate hui: {db.keys_activated_today()}\n"
                f"🚀 Naye hostings live hue: {db.hostings_started_today()}\n"
                f"🖥️ Abhi live: {db.used_slots_count()}/{config.MAX_SLOTS}\n"
                f"💰 Aaj ki kamai (estimated): ₹{db.revenue_today():.0f}\n"
                f"🏦 Total kamai (all-time): ₹{db.all_time_revenue():.0f}\n"
            )
            return text, kb.back_button()
        await spin(query, final)
        return

    if query.data == "admin_slots":
        def final():
            used = db.used_slots_count()
            free = config.MAX_SLOTS - used
            bar = "🟩" * used + "⬜" * max(free, 0)
            text = (
                f"🖥️ *Server / Slots Status*\n\n"
                f"{bar}\n\n"
                f"Used: {used}/{config.MAX_SLOTS}\n"
                f"Free: {free}\n\n"
                + ("✅ Naye slot available hain — new key becho!" if free > 0
                   else "🛑 Server full hai — koi naya slot nahi hai abhi.")
            )
            return text, kb.back_button()
        await spin(query, final)
        return

    if query.data == "admin_pending":
        pending = db.pending_hostings()
        if not pending:
            await ui.edit_menu(query, "📥 Koi pending request nahi hai.", reply_markup=kb.back_button())
            return
        await ui.edit_menu(
            query,
            f"📥 {len(pending)} pending requests hain — check karo apne DMs mein har request ke liye jo alag se bheji gayi thi.",
            reply_markup=kb.back_button(),
        )
        return

    if query.data == "admin_toggle":
        current = db.get_setting("bot_enabled", "1")
        new_val = "0" if current == "1" else "1"
        db.set_setting("bot_enabled", new_val)
        enabled = new_val == "1"
        status = "🟢 ON" if enabled else "🔴 OFF (maintenance mode)"
        await ui.edit_menu(query, f"⚙️ Bot ab {status} hai.", reply_markup=kb.admin_menu(enabled))
        return


async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the multi-step Generate Key conversation typed by admin."""
    if not is_admin(update.effective_user.id):
        return False
    state = context.user_data.get("state")

    if state == GEN_DAYS:
        txt = update.message.text.strip()
        if not txt.isdigit() or int(txt) <= 0:
            await update.message.reply_text("❌ Sahi number bhejo, e.g. 30")
            return True
        days = int(txt)
        category = context.user_data.get("gen_category", "bot")
        rate = config.HOSTING_TYPES[category]["rate_per_day"]
        base_price = days * rate

        surcharge_pct = 0
        if context.user_data.get("gen_vip"):
            surcharge_pct = config.VIP_SURCHARGE_PERCENT
        elif context.user_data.get("gen_priority"):
            surcharge_pct = config.PRIORITY_SURCHARGE_PERCENT
        price = round(base_price * (1 + surcharge_pct / 100), 2)

        context.user_data["gen_days"] = days
        context.user_data["gen_price"] = price
        context.user_data["state"] = GEN_DEVICES
        surcharge_note = f" (base ₹{base_price} + {surcharge_pct}% tier surcharge)" if surcharge_pct else ""
        await update.message.reply_text(
            f"💰 Price: *₹{price}*{surcharge_note}\n\n"
            "📱 Kitne *devices* allow karne hain? (number bhejo, e.g. 1)",
            parse_mode="Markdown",
        )
        return True

    if state == GEN_DEVICES:
        txt = update.message.text.strip()
        if not txt.isdigit():
            await update.message.reply_text("❌ Number bhejo, e.g. 1")
            return True
        context.user_data["gen_devices"] = int(txt)

        prefill = context.user_data.get("gen_username_prefill")
        if prefill is not None:
            await finalize_key(update, context, prefill)
            return True

        context.user_data["state"] = GEN_USERNAME
        await update.message.reply_text("👤 Kis *username* ke naam par key banani hai? (bina @ ke bhejo)",
                                         parse_mode="Markdown")
        return True

    if state == GEN_USERNAME:
        username = update.message.text.strip().lstrip("@")
        await finalize_key(update, context, username)
        return True

    if state == BROADCAST_WAIT:
        context.user_data["state"] = None
        text = update.message.text
        user_ids = db.all_user_ids()
        sent, failed = 0, 0
        for uid in user_ids:
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 {text}")
                sent += 1
            except Exception:
                failed += 1
        await update.message.reply_text(f"✅ Broadcast bhej diya!\n📤 Sent: {sent} | ❌ Failed: {failed}")
        return True

    return False


async def finalize_key(update: Update, context: ContextTypes.DEFAULT_TYPE, username: str):
    days = context.user_data.pop("gen_days")
    devices = context.user_data.pop("gen_devices")
    base_price = context.user_data.pop("gen_price")
    category = context.user_data.pop("gen_category", "bot")
    context.user_data.pop("gen_username_prefill", None)
    target_id_hint = context.user_data.pop("gen_target_id", None)
    context.user_data["state"] = None

    cat_info = config.HOSTING_TYPES[category]
    notes = []

    # renewal discount — if this username has bought this category before
    price = base_price
    if db.has_previous_key(username, category):
        discount = config.RENEWAL_DISCOUNT_PERCENT
        price = round(base_price * (1 - discount / 100), 2)
        notes.append(f"🔁 Renewal discount applied: {discount}% off (₹{base_price} → ₹{price})")

    # referral bonus — free extra days, doesn't change price
    target = db.find_user_by_username(username) or (
        {"user_id": target_id_hint} if target_id_hint else None
    )
    bonus_days = 0
    if target:
        bonus_days = db.pop_bonus_days(target["user_id"])
        if bonus_days:
            notes.append(f"🎁 Referral bonus applied: +{bonus_days} free din (no extra charge)")

    priority = context.user_data.pop("gen_priority", 0)
    vip = context.user_data.pop("gen_vip", 0)

    total_days = days + bonus_days
    code = db.create_key(total_days, devices, username, update.effective_user.id,
                          category=category, price=price, priority=priority, vip=vip)

    tier_txt = " 👑 VIP" if vip else (" ⭐ Priority" if priority else "")
    notes_txt = ("\n" + "\n".join(notes) + "\n") if notes else ""
    await update.message.reply_text(
        f"✅ *Key Generated!*{tier_txt}\n\n"
        f"🔑 `{code}`\n"
        f"{cat_info['label']}\n"
        f"👤 For: @{username}\n"
        f"📅 Days: {total_days}" + (f" ({days} + {bonus_days} bonus)" if bonus_days else "") + "\n"
        f"📱 Devices: {devices}\n"
        f"💰 Price: ₹{price}\n"
        f"{notes_txt}\n"
        f"Ye key sirf ek hi baar use hogi aur sirf @{username} ke account se activate hogi.",
        parse_mode="Markdown",
    )

    if target:
        try:
            await context.bot.send_message(
                chat_id=target["user_id"],
                text=(
                    f"🎉 *Tumhare liye naya Hosting Key aaya hai!*\n\n"
                    f"🔑 `{code}`\n{cat_info['label']}\n📅 Valid: {total_days} din\n\n"
                    f"🔑 Activate Key menu se isse activate karo."
                ),
                parse_mode="Markdown",
            )
        except Exception:
            pass


async def waitlist_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("Ye sirf admin ke liye hai.", show_alert=True)
        return
    await query.answer()

    hosting_id = int(query.data.split("_", 1)[1])
    hosting = db.get_hosting(hosting_id)
    if not hosting:
        await ui.edit_menu(query, "⚠️ Ye request ab exist nahi karti.")
        return

    db.waitlist_hosting(hosting_id)
    await ui.edit_menu(query, f"📋 Request #{hosting_id} waitlist mein daal di gayi.")
    try:
        await context.bot.send_message(
            chat_id=hosting["user_id"],
            text=(
                f"📋 Server abhi full hai, tumhari file `{hosting['filename']}` waitlist mein daal di gayi hai.\n"
                f"Slot free hote hi turant approve ho jayegi — line se, first-come-first-serve."
            ),
            parse_mode="Markdown",
        )
    except Exception:
        pass


async def approval_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("Ye sirf admin ke liye hai.", show_alert=True)
        return
    await query.answer()

    action, hosting_id = query.data.split("_", 1)
    hosting_id = int(hosting_id)
    hosting = db.get_hosting(hosting_id)
    if not hosting:
        await ui.edit_menu(query, "⚠️ Ye request ab exist nahi karti.")
        return

    if action == "reject":
        db.reject_hosting(hosting_id)
        await ui.edit_menu(query, f"❌ Request #{hosting_id} reject kar di gayi.")
        await context.bot.send_message(
            chat_id=hosting["user_id"],
            text=f"❌ Tumhari file `{hosting['filename']}` reject ho gayi hai.",
            parse_mode="Markdown",
        )
        return

    # action == approve
    slot = db.next_free_slot_number()
    if slot is None:
        await ui.edit_menu(
            query,
            f"🛑 Server FULL hai ({config.MAX_SLOTS}/{config.MAX_SLOTS})! Koi slot free nahi hai.\n"
            f"Waitlist mein daal do — slot free hote hi automatically agla notification aayega, "
            f"ek-ek karke line se (bina spam ke).",
            reply_markup=kb.waitlist_button(hosting_id),
        )
        return

    key_row = db.get_key(hosting["key_code"])
    category = hosting["category"]
    port = config.PORT_RANGE_START + slot if category in ("api", "website") else None

    try:
        pid = pm.start_process(hosting_id, hosting["filepath"], hosting["language"],
                                category=category, port=port, vip=bool(hosting["vip"]))
    except Exception as e:
        await ui.edit_menu(query, f"❌ Start karne mein error: {e}")
        return

    db.approve_hosting(hosting_id, pid, slot, key_row["expires_at"], port=port)
    port_txt = f"\n🌐 Port: `{port}`" if port else ""
    tier_txt = " 👑" if hosting["vip"] else (" ⭐" if hosting["priority"] else "")
    await ui.edit_menu(
        query, f"✅ Request #{hosting_id} approved!{tier_txt}\n🖥️ Slot #{slot} assigned. PID: {pid}{port_txt}"
    )
    cat_info = config.HOSTING_TYPES.get(category, {"label": category})
    await context.bot.send_message(
        chat_id=hosting["user_id"],
        text=(
            f"🎉 *Tumhara hosting LIVE ho gaya hai!*\n\n"
            f"{cat_info['label']}\n"
            f"📄 File: `{hosting['filename']}`\n"
            f"🖥️ Slot: #{slot}{port_txt}\n"
            f"⏳ Expires: {key_row['expires_at'][:16].replace('T',' ')}\n\n"
            f"24x7 chal raha hai ab ✅"
        ),
        parse_mode="Markdown",
    )
