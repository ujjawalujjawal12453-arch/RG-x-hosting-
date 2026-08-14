# Ravan X Hosting REST API
Base URL: `/api`.

## Auth
- `POST /auth/register` `{name,email,password}` creates a user, wallet and email verification token.
- `POST /auth/login` returns the current user and sets secure JWT cookies.
- `POST /auth/logout`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/change-password`, `/auth/verify-email`.

## Hosting
- `GET /plans` lists active admin-configured plans.
- `POST /hosting/purchase` verifies wallet balance, debits wallet, creates invoice and provisions Docker when available.
- `GET /hosting` lists user or admin hosting records.
- `POST /hosting/:id/start|stop|restart|delete|logs` controls attached containers.
- `POST /files/:hostingId` uploads files into the hosting workspace.

## Wallet, billing and support
- `GET /wallet`; `POST /topups` with screenshot; `GET /billing/invoices/:id/pdf`; `POST /tickets`; `GET /tickets`.

## Admin and reseller
- `GET /admin/dashboard`; `POST /admin/topups/:id/:status`; `POST /reseller/apply`; `POST /admin/resellers/:id/:status`.
- Generic CRUD: `GET|POST /admin/:model`, `PUT|DELETE /admin/:model/:id` for Prisma resources.
