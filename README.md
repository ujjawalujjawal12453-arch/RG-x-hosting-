# Ravan X Hosting

Production-oriented hosting platform for Python, Node.js and Java apps with Next.js, Express, PostgreSQL, Prisma, Socket.IO, Docker provisioning, wallet billing, top-up approval, reseller workflows and admin CRUD.

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
1. Provision an Ubuntu server with Docker, Docker Compose, Nginx and a DNS A record.
2. Copy `.env.example` to `.env` and replace all secrets, database values, CORS origins and SMTP details.
3. Run `docker compose up -d --build`.
4. Install `nginx/ravan-x.conf`, change `server_name`, then issue TLS certificates with Certbot.
5. Ensure `/var/run/docker.sock` is mounted only on trusted hosts; this is required for live isolated app containers.

If Docker is unavailable, purchases are still recorded but hosting status becomes `NEEDS_SERVER` so the UI/API never pretends the workload is running.
