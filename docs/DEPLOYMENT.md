# Deploying ReTurn (v2)

Recommended production shape:

| Piece | Host |
|---|---|
| Next.js frontend | Vercel |
| Flask API (Docker) | Render |
| PostgreSQL | Neon |
| Proof media | S3 (or another private object store) |

```text
Browser ──https──► Vercel (Next.js)
                     │ same-origin /api/v1 rewrite (FLASK_API_URL)
                     └──https──► Render (Flask + Gunicorn)
                                    ├──► Neon PostgreSQL
                                    └──► private S3 bucket (recommended)
```

There are two deployable applications (`frontend/`, `backend/`) plus managed services. Do not deploy the repository root.

## 1. Environment

Copy `.env.example` for the local reference. Backend production must set:

| Variable | Value |
|---|---|
| `DATABASE_URL` | Neon direct URL, `?sslmode=require` |
| `FLASK_ENV` | `production` |
| `FLASK_SECRET_KEY` | long random value |
| `SESSION_COOKIE_SECURE` | `true` |
| `TRUST_PROXY_HEADERS` | `true` behind one proxy |
| `CORS_ALLOWED_ORIGINS` | the Vercel origin (defence in depth) |
| `SEED_DEMO_DATA` | `false` for real data; `true` only for a demo |
| `SEED_DEMO_DATA_RESET` | `false`; `true` wipes on every start |
| `AUTH_EXPOSE_RESET_TOKENS` | `false` once a real email provider exists |
| `MEDIA_BACKEND` | `s3` for durable proof images |

S3 additionally needs `S3_BUCKET`, `S3_REGION`, optional `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`.

Frontend (Vercel, Production/Preview/Development):

| Variable | Purpose |
|---|---|
| `FLASK_API_URL` | rewrite target, read at build time |
| `API_INTERNAL_URL` | server layout/API calls at runtime |

Never prefix these with `NEXT_PUBLIC_`.

## 2. Deploy the API on Render

1. Push the repository to GitHub.
2. Render → **New → Blueprint** → select the repo. `render.yaml` defines `return-api` from `backend/Dockerfile`.
3. Paste the Neon direct connection string into `DATABASE_URL`.
4. Apply. The container entrypoint runs `flask --app wsgi db upgrade`, creates the bootstrap administrator when `BOOTSTRAP_ADMIN_EMAIL` is set, optionally seeds demo data, then starts Gunicorn on `$PORT`.
5. Verify `https://<api>/api/v1/health` returns `status: ok`.
6. With demo seeding off, create the first administrator as described in section 4 before signing in.

Free instances sleep; warm the health endpoint before a demo.

## 3. Deploy the frontend on Vercel

1. Vercel → **Add New → Project** → import the repo.
2. **Root Directory: `frontend`**.
3. Add `FLASK_API_URL` and `API_INTERNAL_URL` (same API URL).
4. Deploy. Changing the API URL requires a redeploy so the rewrite is rebuilt.

## 4. First administrator and demo data

### Real deployment (no demo data)

Provision the first administrator exactly once, either from the Render **Shell**:

```bash
flask --app wsgi bootstrap-admin --email admin@example.com --name "Operations Admin"
```

or by setting `BOOTSTRAP_ADMIN_EMAIL` (plus optional `BOOTSTRAP_ADMIN_NAME` / `BOOTSTRAP_ADMIN_PASSWORD`) and restarting the service; the entrypoint then runs the same idempotent command.

The command inserts the permission catalogue, rejection codes and vehicle capacity profiles. Without a supplied password it prints a generated one once. It refuses to create a second administrator, so it is safe to leave enabled. Sign in at `/admin` and create service areas, managers and drivers there.

### Demo data

The development reset command is destructive and must never be run against production data:

```bash
python manage.py seed
```

It creates fictional consumers, drivers, managers, an administrator, service areas, orders, an active batch, a suggestion, proof and an exception. Demo password: `ReTurn#2026`.

| Role | Email |
|---|---|
| Administrator | `admin@return.demo` |
| Manager | `manager@return.demo` |
| Drivers | `arjun@return.demo`, `vikram@return.demo` |
| Consumers | `priya@return.demo`, `rahul@return.demo`, `amit@return.demo` |

Before real use: set `SEED_DEMO_DATA=false` and remove demo accounts/data.

## 5. Post-deploy checks

1. `GET /api/v1/health` directly and through the Vercel domain.
2. `GET /api/v1/auth/csrf` sets `rt_csrf` on the Vercel domain.
3. Sign in as each demo role; confirm each lands on its own dashboard.
4. Manager: approve an order, assign or approve a suggestion.
5. Driver: start duty, accept work, complete a delivery with proof.
6. Consumer: see only their own order and tracking.
7. Admin: verify proof, inspect audit and matching settings.
8. Upload a photo and confirm the image loads through the signed media URL.

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| “API could not be reached” | wrong/missing `FLASK_API_URL` at build | set and redeploy |
| login succeeds but dashboard redirects to `/auth` | missing `API_INTERNAL_URL` or Secure cookie over HTTP | set runtime URL; use HTTPS |
| `csrf_failed` | blocked/expired `rt_csrf` | reload and sign in again |
| health degraded | database unreachable | check `DATABASE_URL` and SSL mode |
| proof images disappear after deploy | local media on ephemeral filesystem | configure S3 |
| first request slow | Render free instance asleep | warm the API |

## 7. Security checklist

- [ ] random `FLASK_SECRET_KEY`
- [ ] HTTPS with `SESSION_COOKIE_SECURE=true`
- [ ] `SEED_DEMO_DATA=false` before real data
- [ ] first administrator created with `bootstrap-admin` and demo accounts absent
- [ ] `BOOTSTRAP_ADMIN_PASSWORD` unset (or rotated) after the first boot
- [ ] `AUTH_EXPOSE_RESET_TOKENS=false` in production
- [ ] CORS limited to the real frontend origin
- [ ] S3 bucket private with server-side encryption
- [ ] `.env` not committed
- [ ] demo accounts removed
- [ ] rate limiting moved to a shared store for multiple instances

## 8. Self-hosted Docker

`docker-compose.yml` builds PostgreSQL, Flask and Next.js. It runs migrations and seeds only when the database is empty. Put a TLS reverse proxy in front, set `TRUST_PROXY_HEADERS=true`, and use S3 or a persistent volume for media.
