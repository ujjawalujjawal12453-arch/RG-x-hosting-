# Ravan X Hosting

Ravan X Hosting has two deployment surfaces:

- **`ravan_x_hosting.py`** is the requested single-file Telegram hosting control plane. It can be copied to an Ubuntu server and run directly. It provisions and controls **real Docker containers**; it never reports an app as running when Docker is unavailable.
- **`apps/api` + `apps/web`** is the browser-oriented PostgreSQL/Prisma control plane, with its deployment configuration and API reference retained in this repository.

## Single-file Telegram hosting panel

### What it does

`ravan_x_hosting.py` is intentionally self-contained: its Telegram UI, configuration bootstrap, SQLite persistence, Docker lifecycle integration, project upload, runtime detection, wallet ledger, support tickets, and admin actions live in one Python file.

- On its **first** local run, it asks only for `BOT_TOKEN` and the numeric `ADMIN_ID`, then saves them in a private `.ravan_x_hosting.json` file (`0600` when the operating system permits it). Later starts do not ask again. You can instead set `BOT_TOKEN` and `ADMIN_ID` as environment variables for unattended deployment.
- The primary controls use Telegram's **reply keyboard**, so they appear below the conversation input: Deploy, My Apps, Wallet, Usage, Support, Server, and Admin (admin only).
- Telegram itself does not expose an API for arbitrary button/card colours. The bot uses the native keyboard below chat, emoji state indicators, and clear status messages rather than claiming colour control it cannot perform.
- Upload a `.zip`, `.py`, `.js`, or `.jar`; the bot detects Python, Node.js, or Java and uses Docker to create a resource-limited container (`512m`, `0.50` CPU, PID limit, localhost-only published port). It offers start, stop, restart, logs, usage, and deletion from Telegram.
- If the server has no Docker CLI/access, deploy and server-status actions clearly return the prerequisite instead of inventing a running hosting service.

### Install and run on Ubuntu

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv docker.io
sudo usermod -aG docker "$USER"  # log out/in afterwards so Docker access applies
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python3 ravan_x_hosting.py
```

The first run asks for the bot token and numeric admin Telegram ID exactly once. Keep `.ravan_x_hosting.json`, `ravan_x_data/`, and the source file on persistent storage. Do **not** commit the generated JSON file: it contains the bot token.

For a systemd deployment, use an environment file with `BOT_TOKEN=...` and `ADMIN_ID=...`, run the script as a restricted service user that belongs to the `docker` group, and protect the host: Docker socket access is equivalent to powerful host-level access.

### Real infrastructure boundaries

This bot controls Docker on the machine where it runs. It does not acquire a VPS, DNS records, TLS certificates, payment-gateway credentials, or Telegram token for you. To publish a container publicly, configure DNS and a reverse proxy such as Nginx/Caddy on your server; containers are deliberately bound to `127.0.0.1` by default. The wallet ledger is real local SQLite data; production payment crediting should be wired to a verified gateway webhook, not screenshot automation.

## Browser control plane

The monorepo's Next.js/Express/PostgreSQL stack remains available for browser dashboards, Prisma persistence, invoices, top-up approval, reseller workflows, reverse-proxy config generation and Socket.IO monitoring.

```bash
cp .env.example .env
npm install
npm run prisma:generate
npx prisma migrate dev --name init
npm run seed
npm run dev
```

See [`docs/API.md`](docs/API.md) for REST and realtime endpoints. For production, provision Docker, PostgreSQL, Nginx, DNS, TLS, SMTP, and payment-gateway credentials; then use `docker compose up -d --build` and configure `nginx/ravan-x.conf` for your hostname.
