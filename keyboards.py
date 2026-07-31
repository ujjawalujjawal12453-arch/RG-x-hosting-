"""
Inline keyboards. The "rotating emoji" effect is done by a background job
in bot.py that edits the message text every few seconds, cycling through
frames like 🌑🌒🌓🌔🌕 on a status message - real Telegram messages can't
animate a single emoji by themselves, so we animate by editing.
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

SPINNER_FRAMES = ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"]


def main_menu(is_admin: bool):
    rows = [
        [InlineKeyboardButton("🔑 Activate Key", callback_data="menu_activate")],
        [InlineKeyboardButton("📁 My Hosting", callback_data="menu_myhosting")],
        [
            InlineKeyboardButton("💰 Pricing", callback_data="menu_pricing"),
            InlineKeyboardButton("💳 Buy Key", callback_data="menu_buy"),
        ],
        [InlineKeyboardButton("👥 Refer & Earn", callback_data="menu_referral")],
        [InlineKeyboardButton("🎁 Free Trial (1 din)", callback_data="menu_trial")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="menu_help")],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="menu_admin")])
    return InlineKeyboardMarkup(rows)


def tier_picker():
    import config
    rows = [
        [InlineKeyboardButton("⚪ Standard", callback_data="gentier_standard")],
        [InlineKeyboardButton(f"⭐ Priority (+{config.PRIORITY_SURCHARGE_PERCENT}%)", callback_data="gentier_priority")],
        [InlineKeyboardButton(f"👑 VIP (+{config.VIP_SURCHARGE_PERCENT}%)", callback_data="gentier_vip")],
        [InlineKeyboardButton("⬅️ Back", callback_data="admin_genkey")],
    ]
    return InlineKeyboardMarkup(rows)


def category_picker():
    import config
    rows = []
    for cat, info in config.HOSTING_TYPES.items():
        rows.append([InlineKeyboardButton(
            f"{info['label']} (₹{info['rate_per_day']}/din)", callback_data=f"gencat_{cat}"
        )])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="menu_admin")])
    return InlineKeyboardMarkup(rows)


def quickgen_button(user_id: int, username: str):
    label = f"🆕 Generate Key for @{username}" if username else f"🆕 Generate Key (id {user_id})"
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(label, callback_data=f"quickgen_{user_id}_{username}")]]
    )


def unban_buttons(banned_rows):
    rows = []
    for r in banned_rows:
        label = f"✅ Unban @{r['username'] or r['user_id']}"
        rows.append([InlineKeyboardButton(label, callback_data=f"unban_{r['user_id']}")])
    rows.append([InlineKeyboardButton("⬅️ Back", callback_data="menu_admin")])
    return InlineKeyboardMarkup(rows)


def admin_menu(bot_enabled: bool):
    toggle_label = "🔴 Turn Bot OFF" if bot_enabled else "🟢 Turn Bot ON"
    rows = [
        [InlineKeyboardButton("🆕 Generate Key", callback_data="admin_genkey")],
        [InlineKeyboardButton("📊 Today's Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("🖥️ Server / Slots Status", callback_data="admin_slots")],
        [InlineKeyboardButton("📥 Pending Approvals", callback_data="admin_pending")],
        [InlineKeyboardButton("📢 Broadcast to All Users", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🚫 Banned Users", callback_data="admin_banned")],
        [InlineKeyboardButton(toggle_label, callback_data="admin_toggle")],
        [InlineKeyboardButton("⬅️ Back", callback_data="menu_back")],
    ]
    return InlineKeyboardMarkup(rows)


def waitlist_button(hosting_id: int):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("📋 Add to Waitlist", callback_data=f"waitlist_{hosting_id}")]]
    )


def approval_buttons(hosting_id: int):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve & Host", callback_data=f"approve_{hosting_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{hosting_id}"),
            ]
        ]
    )


def back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Back", callback_data="menu_back")]])
