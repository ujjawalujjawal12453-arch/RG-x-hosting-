# Ravan X Hosting REST API
Base URL: `/api`. All private endpoints use JWT access cookies and role-based middleware.

## Auth
- `POST /auth/register` `{name,email,password}` creates a user, wallet and email verification token.
- `POST /auth/login` sets secure HTTP-only access and refresh cookies.
- `POST /auth/logout`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/change-password`, `/auth/verify-email`.

## Hosting lifecycle
- `GET /plans` lists active admin-configured plans.
- `POST /hosting/purchase` verifies wallet balance, debits wallet, creates invoice, allocates workspace/port and provisions Docker when available.
- `GET /hosting` lists user or admin hosting records.
- `POST /hosting/:id/start|stop|restart|delete|logs|suspend|unsuspend|stats` controls attached containers.
- `POST /hosting/:id/reverse-proxy` writes an Nginx app config for the allocated port and selected domain.

## File manager
- `GET /files/:hostingId?path=` lists workspace files.
- `POST /files/:hostingId/upload` uploads project files.
- `GET /files/:hostingId/read?path=`, `POST /files/:hostingId/write`, `POST /files/:hostingId/folder`.
- `POST /files/:hostingId/rename`, `DELETE /files/:hostingId?path=`, `POST /files/:hostingId/compress`, `GET /files/:hostingId/download?path=`.

## Wallet, billing and support
- `GET /wallet` returns balance and transactions.
- `POST /topups` accepts payment screenshots for admin approval.
- `GET /billing/invoices/:id/pdf` streams a PDF invoice.
- `POST /tickets`, `GET /tickets` implement support ticketing.

## Admin and reseller
- `GET /admin/dashboard` aggregates users, hosting, revenue, pending top-ups/resellers, tickets and recent activity.
- `POST /admin/topups/:id/:status` approves/rejects top-ups and credits approved wallets.
- `POST /reseller/apply` enforces the ₹1500 minimum wallet rule.
- `POST /admin/resellers/:id/:status` grants or revokes reseller role and 30-day validity.
- Generic CRUD: `GET|POST /admin/:model`, `PUT|DELETE /admin/:model/:id` for Prisma resources.

## Realtime Socket.IO
- `metrics` broadcasts server/platform telemetry.
- `logs:join` streams Docker logs for a hosting record with an attached container.
- `console:command` provides a controlled live-console hook for trusted deployments.
