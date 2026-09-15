#!/usr/bin/env python3
"""Ravan X Hosting — single-file Telegram Docker hosting control plane.

On first run it asks only for a Telegram bot token and the numeric admin ID, then
stores them in .ravan_x_hosting.json. It uses SQLite locally and Docker CLI on the
same Ubuntu server. If Docker is unavailable, it reports that fact and never marks
an application as running.
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import time
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "ravan_x_data"
APPS = DATA / "apps"
CONFIG_FILE = ROOT / ".ravan_x_hosting.json"
DATABASE = DATA / "ravan_x.db"
LOG = logging.getLogger("ravan-x")
APP_NAME = re.compile(r"^[a-z][a-z0-9-]{2,30}$")

MAIN_MENU = [["🚀 Deploy", "🖥 My Apps"], ["💳 Wallet", "📈 Usage"], ["🆘 Support", "ℹ️ Server"]]
ADMIN_MENU = [["👑 Admin", "🚀 Deploy", "🖥 My Apps"], ["💳 Wallet", "📈 Usage"], ["🆘 Support", "ℹ️ Server"]]

@dataclass(frozen=True)
class Settings:
    token: str
    admin_id: int


def load_settings() -> Settings:
    """Bootstrap once. Environment variables take precedence for deployment."""
    token, admin = os.getenv("BOT_TOKEN", ""), os.getenv("ADMIN_ID", "")
    if not (token and admin) and CONFIG_FILE.exists():
        saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        token, admin = token or str(saved.get("bot_token", "")), admin or str(saved.get("admin_id", ""))
    if not token:
        token = input("Telegram BOT_TOKEN (asked only once): ").strip()
    if not admin:
        admin = input("Telegram numeric ADMIN_ID (asked only once): ").strip()
    if not token or not admin.isdigit():
        raise SystemExit("BOT_TOKEN and numeric ADMIN_ID are required.")
    settings = Settings(token, int(admin))
    CONFIG_FILE.write_text(json.dumps({"bot_token": token, "admin_id": settings.admin_id}, indent=2), encoding="utf-8")
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass
    return settings

SETTINGS = load_settings()


def db() -> sqlite3.Connection:
    DATA.mkdir(exist_ok=True); APPS.mkdir(exist_ok=True)
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row
    return con


def init_db() -> None:
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY, username TEXT, wallet_paise INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS apps (id TEXT PRIMARY KEY, owner_id INTEGER NOT NULL, name TEXT UNIQUE NOT NULL, runtime TEXT NOT NULL, container_id TEXT, status TEXT NOT NULL, port INTEGER, created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS transactions (id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, amount_paise INTEGER NOT NULL, kind TEXT NOT NULL, note TEXT, created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS topups (id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, amount_paise INTEGER NOT NULL, status TEXT NOT NULL, proof_path TEXT, created_at INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS tickets (id TEXT PRIMARY KEY, user_id INTEGER NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'OPEN', created_at INTEGER NOT NULL);
        """)


def docker(*args: str, timeout: int = 90) -> tuple[bool, str]:
    """Run Docker locally. This is the only container control path; no simulated state."""
    if not shutil.which("docker"):
        return False, "Docker CLI is not installed. Install Docker on this Ubuntu server and give this user Docker access."
    try:
        result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Docker command failed: {exc}"
    text = (result.stdout or result.stderr).strip()
    return result.returncode == 0, text or "Docker completed without output."


def runtime_for(path: Path) -> str | None:
    names = {p.name.lower() for p in path.rglob("*") if p.is_file()}
    if "package.json" in names: return "node"
    if "requirements.txt" in names or any(n.endswith(".py") for n in names): return "python"
    if "pom.xml" in names or "build.gradle" in names or any(n.endswith(".jar") for n in names): return "java"
    return None


def boot_command(runtime: str, source: Path) -> tuple[str, str]:
    if runtime == "python":
        main = "main.py" if (source / "main.py").exists() else "app.py"
        return "python:3.12-slim", f"pip install --no-cache-dir -r requirements.txt 2>/dev/null || true; python {main}"
    if runtime == "node":
        return "node:22-alpine", "npm ci --omit=dev || npm install --omit=dev; npm start"
    jar = next(source.glob("*.jar"), None)
    if jar: return "eclipse-temurin:21-jre", f"java -jar {jar.name}"
    return "maven:3-eclipse-temurin-21", "mvn -q -DskipTests package && java -jar target/*.jar"


def money(paise: int) -> str: return f"₹{paise / 100:,.2f}"
def is_admin(user_id: int) -> bool: return user_id == SETTINGS.admin_id
def menu(user_id: int) -> ReplyKeyboardMarkup: return ReplyKeyboardMarkup(ADMIN_MENU if is_admin(user_id) else MAIN_MENU, resize_keyboard=True)
def upsert_user(tg_id: int, username: str | None) -> None:
    with db() as con: con.execute("INSERT INTO users(telegram_id, username, created_at) VALUES(?,?,?) ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username", (tg_id, username or "", int(time.time())))


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user; assert user and update.message
    upsert_user(user.id, user.username)
    text = "⚡ *Ravan X Hosting Control Plane*\n\nDeploy Python, Node.js, or Java projects to real Docker containers from Telegram. Upload a ZIP using *🚀 Deploy*."
    if is_admin(user.id): text += "\n\n👑 Admin controls are enabled for this account."
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=menu(user.id))


async def server_status(update: Update, context: ContextTypes.DEFAULT_TYPE | None = None) -> None:
    assert update.message
    ok, out = docker("info", "--format", "{{.ServerVersion}} | {{.ContainersRunning}} running containers")
    await update.message.reply_text(f"{'🟢' if ok else '🔴'} *Server status*\n{out}", parse_mode="Markdown", reply_markup=menu(update.effective_user.id))


async def deploy_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    context.user_data["flow"] = "deploy_file"
    await update.message.reply_text("📦 Send one project file now: a `.zip`, `.py`, `.js`, or `.jar`. I will detect the runtime and then ask for an app name.", reply_markup=menu(update.effective_user.id))


async def document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message and update.message.document and update.effective_user
    if context.user_data.get("flow") != "deploy_file":
        await update.message.reply_text("Use *🚀 Deploy* first, then send your project file.", parse_mode="Markdown")
        return
    doc = update.message.document
    filename = Path(doc.file_name or "upload").name
    if Path(filename).suffix.lower() not in {".zip", ".py", ".js", ".jar"}:
        await update.message.reply_text("Only .zip, .py, .js, or .jar uploads are supported."); return
    incoming = DATA / "incoming" / f"{uuid.uuid4()}-{filename}"; incoming.parent.mkdir(parents=True, exist_ok=True)
    await (await doc.get_file()).download_to_drive(incoming)
    context.user_data["upload"] = str(incoming); context.user_data["flow"] = "deploy_name"
    await update.message.reply_text("✅ File received. Send an app name using lowercase letters, digits and hyphens (example: `my-api`).", parse_mode="Markdown")


def prepare_source(upload: Path, name: str) -> tuple[Path, str | None]:
    source = APPS / name / "source"
    shutil.rmtree(source.parent, ignore_errors=True); source.mkdir(parents=True)
    if upload.suffix.lower() == ".zip":
        with zipfile.ZipFile(upload) as archive:
            for member in archive.infolist():
                target = (source / member.filename).resolve()
                if not str(target).startswith(str(source.resolve())): raise ValueError("Unsafe ZIP path.")
            archive.extractall(source)
        children = list(source.iterdir())
        if len(children) == 1 and children[0].is_dir():
            nested = children[0]; [shutil.move(str(p), source) for p in nested.iterdir()]; nested.rmdir()
    else: shutil.copy2(upload, source / upload.name)
    return source, runtime_for(source)


async def create_deployment(update: Update, context: ContextTypes.DEFAULT_TYPE, name: str) -> None:
    assert update.message and update.effective_user
    upload_text = context.user_data.pop("upload", None); context.user_data.pop("flow", None)
    if not upload_text or not APP_NAME.fullmatch(name):
        await update.message.reply_text("Invalid deployment request. App names must be 3–31 lowercase letters, digits, or hyphens."); return
    with db() as con:
        if con.execute("SELECT 1 FROM apps WHERE name=?", (name,)).fetchone():
            await update.message.reply_text("That app name is already in use. Choose another."); return
    try: source, runtime = prepare_source(Path(upload_text), name)
    except (ValueError, zipfile.BadZipFile) as exc:
        await update.message.reply_text(f"Upload could not be unpacked: {exc}"); return
    if not runtime:
        shutil.rmtree(source.parent, ignore_errors=True); await update.message.reply_text("Could not detect Python, Node.js, or Java. Include requirements.txt, package.json, pom.xml/build.gradle, or a supported source file."); return
    image, command = boot_command(runtime, source); cname = f"ravanx-{name}"
    await update.message.chat.send_action(ChatAction.TYPING)
    ok, out = docker("run", "-d", "--name", cname, "--restart", "unless-stopped", "--memory", "512m", "--cpus", "0.50", "--pids-limit", "256", "-p", "127.0.0.1::8000", "-v", f"{source.resolve()}:/app", "-w", "/app", image, "sh", "-c", command, timeout=120)
    now = int(time.time())
    if not ok:
        shutil.rmtree(source.parent, ignore_errors=True)
        await update.message.reply_text(f"🔴 Deployment was *not* created.\n\n{out}", parse_mode="Markdown"); return
    cid = out.splitlines()[-1]
    ok_port, port_out = docker("port", cid, "8000/tcp")
    match = re.search(r":(\d+)$", port_out) if ok_port else None
    with db() as con: con.execute("INSERT INTO apps VALUES(?,?,?,?,?,?,?,?,?)", (str(uuid.uuid4()), update.effective_user.id, name, runtime, cid, "RUNNING", int(match.group(1)) if match else None, now, now))
    await update.message.reply_text(f"🟢 *{name}* deployed as a real `{runtime}` Docker container.\nContainer: `{cid[:12]}`\nPort: `{match.group(1) if match else 'not published'}`\n\nUse *🖥 My Apps* for start/stop/logs/delete.", parse_mode="Markdown", reply_markup=menu(update.effective_user.id))


async def apps_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message and update.effective_user
    with db() as con: rows = con.execute("SELECT * FROM apps WHERE owner_id=? AND status!='DELETED' ORDER BY created_at DESC", (update.effective_user.id,)).fetchall()
    if not rows:
        await update.message.reply_text("No deployments yet. Press *🚀 Deploy* and upload your project ZIP.", parse_mode="Markdown", reply_markup=menu(update.effective_user.id)); return
    buttons = [[InlineKeyboardButton(f"{r['name']} · {r['status']}", callback_data=f"app:{r['id']}")] for r in rows]
    await update.message.reply_text("🖥 *Your real Docker deployments*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))


async def app_panel(query, app: sqlite3.Row) -> None:
    actions = [[InlineKeyboardButton("▶ Start", callback_data=f"act:start:{app['id']}"), InlineKeyboardButton("⏹ Stop", callback_data=f"act:stop:{app['id']}")], [InlineKeyboardButton("🔄 Restart", callback_data=f"act:restart:{app['id']}"), InlineKeyboardButton("📜 Live logs", callback_data=f"act:logs:{app['id']}")], [InlineKeyboardButton("🗑 Delete", callback_data=f"act:delete:{app['id']}")]]
    await query.edit_message_text(f"*{app['name']}*\nRuntime: `{app['runtime']}`\nStatus: *{app['status']}*\nContainer: `{(app['container_id'] or 'none')[:12]}`\nPort: `{app['port'] or 'not published'}`\n\nActions talk to Docker directly.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(actions))


async def callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query; assert query and query.from_user
    await query.answer(); data = query.data or ""
    if data.startswith("app:"):
        with db() as con: app = con.execute("SELECT * FROM apps WHERE id=? AND owner_id=?", (data[4:], query.from_user.id)).fetchone()
        if app: await app_panel(query, app)
        return
    if not data.startswith("act:"): return
    _, action, app_id = data.split(":", 2)
    with db() as con: app = con.execute("SELECT * FROM apps WHERE id=? AND owner_id=?", (app_id, query.from_user.id)).fetchone()
    if not app: await query.edit_message_text("Deployment not found."); return
    cid = app["container_id"]
    if action == "logs":
        ok, out = docker("logs", "--tail", "70", cid, timeout=20); await query.message.reply_text(f"📜 *{app['name']} logs*\n```\n{out[-3500:]}\n```", parse_mode="Markdown"); return
    if action == "delete":
        ok, out = docker("rm", "-f", cid); status = "DELETED" if ok else app["status"]
        if ok: shutil.rmtree(APPS / app["name"], ignore_errors=True)
    else:
        cmd = {"start": "start", "stop": "stop", "restart": "restart"}[action]; ok, out = docker(cmd, cid); status = {"start": "RUNNING", "stop": "STOPPED", "restart": "RUNNING"}[action] if ok else app["status"]
    with db() as con: con.execute("UPDATE apps SET status=?, updated_at=? WHERE id=?", (status, int(time.time()), app_id))
    await query.message.reply_text(f"{'✅' if ok else '🔴'} {action.title()} *{app['name']}*\n{out}", parse_mode="Markdown")


async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE | None = None) -> None:
    assert update.message and update.effective_user
    with db() as con:
        user = con.execute("SELECT wallet_paise FROM users WHERE telegram_id=?", (update.effective_user.id,)).fetchone()
        tx = con.execute("SELECT amount_paise,kind,note FROM transactions WHERE user_id=? ORDER BY created_at DESC LIMIT 5", (update.effective_user.id,)).fetchall()
    history = "\n".join(f"• {r['kind']}: {money(r['amount_paise'])} {r['note'] or ''}" for r in tx) or "No transactions."
    await update.message.reply_text(f"💳 *Wallet balance:* {money(user['wallet_paise'])}\n\n*Recent activity*\n{history}\n\nFor live payments, connect a verified payment gateway/webhook. Screenshot-only top-ups are pending admin approval and are not auto-credited.", parse_mode="Markdown", reply_markup=menu(update.effective_user.id))


async def usage(update: Update, context: ContextTypes.DEFAULT_TYPE | None = None) -> None:
    assert update.message and update.effective_user
    with db() as con: rows = con.execute("SELECT name,container_id,status FROM apps WHERE owner_id=? AND status!='DELETED'", (update.effective_user.id,)).fetchall()
    lines=[]
    for r in rows:
        if not r['container_id']: lines.append(f"• {r['name']}: {r['status']}"); continue
        ok, output = docker("stats", "--no-stream", "--format", "{{.CPUPerc}} CPU · {{.MemUsage}}", r['container_id'], timeout=15)
        lines.append(f"• *{r['name']}*: {output if ok else r['status']}")
    await update.message.reply_text("📈 *Live Docker usage*\n" + ("\n".join(lines) or "No deployments."), parse_mode="Markdown", reply_markup=menu(update.effective_user.id))


async def support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message
    context.user_data['flow']='support'
    await update.message.reply_text("Describe the issue in one message. It will be stored as a support ticket for the admin.")


async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message and update.effective_user
    if not is_admin(update.effective_user.id): await update.message.reply_text("Admin access required."); return
    with db() as con:
        users=con.execute("SELECT COUNT(*) n FROM users").fetchone()['n']; apps=con.execute("SELECT COUNT(*) n FROM apps WHERE status='RUNNING'").fetchone()['n']; tickets=con.execute("SELECT COUNT(*) n FROM tickets WHERE status='OPEN'").fetchone()['n']; pending=con.execute("SELECT COUNT(*) n FROM topups WHERE status='PENDING'").fetchone()['n']
    context.user_data['flow']='admin_command'
    await update.message.reply_text(f"👑 *Admin control*\nUsers: `{users}` · Running apps: `{apps}` · Open tickets: `{tickets}` · Pending top-ups: `{pending}`\n\nSend one admin command:\n`credit TELEGRAM_ID AMOUNT`\n`apps`\n`tickets`\n`topups`\n`approve TOPUP_ID`\n\nOnly the configured admin can use these commands.", parse_mode="Markdown", reply_markup=menu(update.effective_user.id))


async def text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.message and update.effective_user
    value = (update.message.text or "").strip(); upsert_user(update.effective_user.id, update.effective_user.username)
    routes = {"🚀 Deploy": deploy_prompt, "🖥 My Apps": apps_list, "💳 Wallet": wallet, "📈 Usage": usage, "🆘 Support": support, "ℹ️ Server": server_status, "👑 Admin": admin}
    if value in routes: await routes[value](update, context); return
    flow=context.user_data.get('flow')
    if flow=='deploy_name': await create_deployment(update, context, value); return
    if flow=='support':
        with db() as con: con.execute("INSERT INTO tickets VALUES(?,?,?,?,?)", (str(uuid.uuid4())[:8], update.effective_user.id, value[:2000], 'OPEN', int(time.time())))
        context.user_data.pop('flow',None); await update.message.reply_text("✅ Ticket saved. The admin can review it from *👑 Admin*.", parse_mode='Markdown', reply_markup=menu(update.effective_user.id)); return
    if flow=='admin_command' and is_admin(update.effective_user.id):
        await admin_command(update, context, value); return
    await update.message.reply_text("Choose a button below the chat to manage hosting.", reply_markup=menu(update.effective_user.id))


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE, value: str) -> None:
    assert update.message
    parts=value.split()
    with db() as con:
        if len(parts)==3 and parts[0].lower()=='credit' and parts[1].isdigit():
            try: amount=round(float(parts[2])*100)
            except ValueError: amount=0
            if amount<=0: await update.message.reply_text("Amount must be positive."); return
            uid=int(parts[1]); con.execute("INSERT INTO users(telegram_id,username,created_at) VALUES(?,?,?) ON CONFLICT(telegram_id) DO NOTHING",(uid,'',int(time.time()))); con.execute("UPDATE users SET wallet_paise=wallet_paise+? WHERE telegram_id=?",(amount,uid)); con.execute("INSERT INTO transactions VALUES(?,?,?,?,?,?)",(str(uuid.uuid4()),uid,amount,'CREDIT','Admin credit',int(time.time())))
            await update.message.reply_text(f"✅ Credited {money(amount)} to `{uid}`.",parse_mode='Markdown'); return
        if parts[0].lower()=='apps': rows=con.execute("SELECT name,owner_id,status FROM apps ORDER BY created_at DESC LIMIT 30").fetchall(); await update.message.reply_text("\n".join(f"• {r['name']} · {r['status']} · `{r['owner_id']}`" for r in rows) or "No apps.",parse_mode='Markdown'); return
        if parts[0].lower()=='tickets': rows=con.execute("SELECT id,user_id,message FROM tickets WHERE status='OPEN' ORDER BY created_at DESC LIMIT 20").fetchall(); await update.message.reply_text("\n\n".join(f"#{r['id']} · `{r['user_id']}`\n{r['message']}" for r in rows) or "No open tickets.",parse_mode='Markdown'); return
        if parts[0].lower()=='topups': rows=con.execute("SELECT id,user_id,amount_paise FROM topups WHERE status='PENDING'").fetchall(); await update.message.reply_text("\n".join(f"{r['id']} · `{r['user_id']}` · {money(r['amount_paise'])}" for r in rows) or "No pending top-ups.",parse_mode='Markdown'); return
    await update.message.reply_text("Unknown command. Use `credit ID AMOUNT`, `apps`, `tickets`, or `topups`.",parse_mode='Markdown')


async def error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None: LOG.exception("Telegram update failed", exc_info=context.error)

def main() -> None:
    init_db()
    app = Application.builder().token(SETTINGS.token).concurrent_updates(64).build()
    app.add_error_handler(error); app.add_handler(CommandHandler("start", start)); app.add_handler(CallbackQueryHandler(callback)); app.add_handler(MessageHandler(filters.Document.ALL, document)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text))
    LOG.info("Ravan X Telegram hosting control plane is starting.")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__': main()
