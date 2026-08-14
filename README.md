# Ravan X Hosting

Ravan X Hosting is a production-oriented hosting control panel for Python, Node.js and Java apps. It includes a cyber glassmorphism Next.js interface, Express REST APIs, PostgreSQL/Prisma persistence, wallet billing, top-up approval, reseller workflows, PDF invoices, support tickets, Docker provisioning, file management, reverse-proxy config generation and Socket.IO monitoring.

## What is real vs. infrastructure-dependent
The platform stores real users, wallets, plans, hosting records, invoices, tickets, top-ups, resellers and audit logs in PostgreSQL. On a compatible Ubuntu server with Docker, the API can create/start/stop/restart/delete/suspend/unsuspend containers, allocate CPU/RAM/storage, bind ports, stream logs and write Nginx reverse-proxy configs. If Docker is unavailable, hosting records are marked `NEEDS_SERVER` and the API returns a clear infrastructure requirement.

## Quick start
```bash
cp .env.example .env
npm install
npm run prisma:generate
npx prisma migrate dev --name init
npm run seed
npm run dev
```

Default seeded admin: `admin@ravanx.host` / `Admin@12345`.

## Production deployment
1. Provision Ubuntu with Docker, Docker Compose, Nginx, DNS and a PostgreSQL-compatible database.
2. Copy `.env.example` to `.env`; replace JWT/cookie secrets, CORS origins, database URL, SMTP values and public API/socket URLs.
3. Run `docker compose up -d --build`.
4. Install `nginx/ravan-x.conf`, set `server_name`, validate with `nginx -t`, then issue TLS certificates using Certbot.
5. Mount `/var/run/docker.sock` only on trusted hosts; access to it is powerful and required for live app containers.
6. Point `NGINX_APPS_DIR` at an included Nginx directory if hosted app reverse-proxy snippets should be generated automatically.

## Main modules
- `apps/api`: Express, TypeScript, Prisma, security middleware, Docker/file/reverse-proxy services and Socket.IO.
- `apps/web`: Next.js App Router, Tailwind, premium cyber UI components, landing page, dashboards and auth screens.
- `prisma`: schema, SQL migration and seed data.
- `docs/API.md`: REST and realtime API reference.
