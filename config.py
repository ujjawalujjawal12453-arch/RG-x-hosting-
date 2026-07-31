import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _p(*parts):
    """Resolves a default path relative to the project root — so bot.py and
    website/app.py always agree on where data/ lives, no matter which
    directory each one is launched from."""
    return os.path.join(BASE_DIR, *parts)


# ==== REQUIRED SETTINGS (fill these in your .env file) ====
BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # your Telegram numeric user id

# ==== HOSTING SETTINGS ====
MAX_SLOTS = int(os.getenv("MAX_SLOTS", "10"))          # total hosting slots on this VPS
DB_PATH = os.getenv("DB_PATH", _p("data", "bot.db"))
USER_FILES_DIR = os.getenv("USER_FILES_DIR", _p("data", "user_files"))
QR_IMAGE_PATH = os.getenv("QR_IMAGE_PATH", _p("data", "qr", "payment_qr.png"))
LOGO_IMAGE_PATH = os.getenv("LOGO_IMAGE_PATH", _p("data", "branding", "logo.png"))

# how often (seconds) the background job checks for expired hostings
EXPIRY_CHECK_INTERVAL = 60

# allowed uploaded file extensions -> how to run them
RUNNERS = {
    ".py": ["python3"],
    ".js": ["node"],
}

# ==== 3 HOSTING CATEGORIES + auto price-per-day (in INR — change freely) ====
# price for a key = days * rate. Edit these numbers to your actual rates.
HOSTING_TYPES = {
    "bot":     {"label": "🤖 Bot Hosting",     "rate_per_day": 5,  "exts": [".py", ".js"]},
    "api":     {"label": "🔌 API Hosting",     "rate_per_day": 8,  "exts": [".py", ".js"]},
    "website": {"label": "🌐 Website Hosting", "rate_per_day": 3,  "exts": [".zip", ".html"]},
}

# API / website hosted processes get a real port assigned from this pool
PORT_RANGE_START = 20000

# ==== RULES & REGULATIONS (violation strikes -> auto-ban) ====
MAX_VIOLATIONS_BEFORE_BAN = 3      # 3 strikes and the user is auto-banned
WRONG_KEY_ATTEMPT_LIMIT = 5        # too many wrong-key tries in one session = 1 strike (anti-bruteforce)
PHOTO_SPAM_LIMIT = 4               # more than this many screenshots...
PHOTO_SPAM_WINDOW_SECONDS = 60     # ...within this window = 1 strike (protects admin from notification floods)

# ==== EARNINGS FEATURES ====
REFERRAL_BONUS_DAYS_REFERRER = 3   # free days credited to whoever invited someone
REFERRAL_BONUS_DAYS_REFERRED = 2   # free days credited to the new user who joined via referral
RENEWAL_DISCOUNT_PERCENT = 20      # % off suggested price when a username buys the same category again

# ⭐ Priority Slot — jumps the waitlist queue when server is full, costs extra
PRIORITY_SURCHARGE_PERCENT = 30

# 👑 VIP tier — priority queue-jump + bigger resource limit, costs more than priority
VIP_SURCHARGE_PERCENT = 75
VIP_MEM_LIMIT_MB = 1024            # vs PROCESS_MEM_LIMIT_MB for standard users

# 🎁 Free Trial — 1 day, limited concurrent trial slots, ONE per Telegram user
# (checked server-side against the database — nothing here trusts the client)
TRIAL_ENABLED = True
TRIAL_DAYS = 1
TRIAL_CATEGORY = "bot"
TRIAL_MAX_CONCURRENT = 2           # only this many trial hostings can run at once
TRIAL_KEY_LENGTH = 16              # trial keys are 16 digits (paid keys stay 8)
TRIAL_TOKEN_EXPIRY_SECONDS = 900   # 15 min to finish the locker task + PIN after claiming

# ==== LINK LOCKER (task-to-unlock, e.g. GPLinks / Linkvertise / Lootlabs) ====
# Sign up with whichever service you use, put its API key here. If left
# blank, the locker step is skipped automatically (useful for testing).
LINKLOCKER_ENABLED = bool(os.getenv("LINKLOCKER_API_KEY"))
LINKLOCKER_API_KEY = os.getenv("LINKLOCKER_API_KEY", "")
# Default format matches GPLinks' simple GET API. If you use a different
# provider, check ITS docs and adjust linklocker.py — every locker service
# has a slightly different request/response shape.
LINKLOCKER_API_BASE = os.getenv("LINKLOCKER_API_BASE", "https://api.gplinks.com/api")

# ==== WEBSITE (PIN-verified, task-gated free-trial claim page) ====
WEB_HOST = os.getenv("WEB_HOST", "0.0.0.0")
WEB_PORT = int(os.getenv("PORT", os.getenv("WEB_PORT", "5000")))  # Render injects PORT itself
WEB_SECRET_KEY = os.getenv("WEB_SECRET_KEY", "change-this-to-something-random")
# Set this to your real Render URL once deployed, e.g. https://um-modeoff.onrender.com
# The locker link redirects back here after the task is done, so this MUST be correct.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:5000")
PIN_LENGTH = 6
PIN_EXPIRY_SECONDS = 300           # 5 minutes to enter the PIN
PIN_MAX_ATTEMPTS = 3               # wrong PIN 3 times = treated as a bypass attempt -> violation strike

# max resident memory (MB) and cpu seconds a hosted process may use (best-effort limit)
PROCESS_MEM_LIMIT_MB = 512
PROCESS_CPU_LIMIT_SEC = 3600 * 24  # 24h cpu-time ceiling as a safety net
