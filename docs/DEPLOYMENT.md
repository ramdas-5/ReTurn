# Deploying ReTurn

ReTurn is a two-service application. The recommended production shape is:

| Piece | Host | Why |
|---|---|---|
| Next.js frontend | **Vercel** | Native Next.js 15 support, HTTPS, CDN, zero-config rewrites |
| Flask API (Docker) | **Render** (free web service) | Runs the supplied `backend/Dockerfile`, HTTPS, health checks |
| PostgreSQL | **Neon** (free tier) | Managed PostgreSQL 16+, persistent, works with Alembic |

```text
Browser ──https──► Vercel (Next.js)
                     │  same-origin rewrite /api/v1/*  (FLASK_API_URL)
                     └──https──► Render (Flask + Gunicorn)
                                    │
                                    └──► Neon PostgreSQL
```

The browser only ever talks to the Vercel domain. `rt_session` and `rt_csrf`
stay first-party cookies; Flask remains the only authority for auth, RBAC,
matching and writes.

> **Mental model:** there are exactly **two deployable apps** (`frontend/` and
> `backend/`) plus one managed database. Do not deploy the repository root.

---

## 1. What was changed to make this deploy-ready

| File | Change |
|---|---|
| `frontend/next.config.ts` | `output: "standalone"` is skipped on Vercel (`VERCEL` env); trailing slash trimmed from `FLASK_API_URL` |
| `frontend/vercel.json` | Pins the Next.js framework, `npm ci` install and `npm run build` |
| `frontend/src/app/page.tsx` | Landing page still renders if the API is cold/unreachable |
| `backend/docker-entrypoint.sh` | Binds `0.0.0.0:$PORT` (Render/Railway), runs migrations, seeds only when empty |
| `backend/app/config.py` | Accepts `postgres://` / `postgresql://` URLs and converts them to `postgresql+psycopg://`; `Secure` cookies default on when `FLASK_ENV=production`; proxy trust flag |
| `backend/app/__init__.py` | Optional `ProxyFix` so client IPs and schemes are correct behind Render/Vercel |
| `backend/manage.py` | New `seed-if-empty` command (restart-safe seeding) |
| `backend/.dockerignore` | Keeps `.venv`, `.pgdata`, `.env`, tests and caches out of the image |
| `.gitattributes` | Forces LF line endings for `.sh`/Docker files so Windows clones still run in Linux containers |
| `render.yaml` | Render Blueprint for the API service |
| `.env.example` | Documents `TRUST_PROXY_HEADERS`, `SEED_DEMO_DATA`, `SEED_DEMO_DATA_RESET` |

Verified locally during this change: 27/27 pytest tests pass, `tsc --noEmit`
passes, a Vercel-style `next build` passes, and the Docker image boots against
PostgreSQL with `PORT=10000`, runs Alembic, seeds once, and answers
`GET /api/v1/health` with **200**.

---

## 2. Manual tasks you must do (nothing can automate these)

You need accounts on three services. Everything below is manual browser work.

### 2.1 Create a Neon PostgreSQL database

1. Go to <https://neon.tech> → **Sign up** (GitHub login is fine).
2. **Create project** → name it `return` → PostgreSQL version **16 or newer**.
3. Open **Connect** (or **Connection Details**) and copy the **direct** connection string, e.g.
   `postgresql://return_owner:AbC123@ep-cool-name-123456.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`
4. Keep `?sslmode=require` on the end. **Do not** use the pooled `-pooler`
   hostname; the app runs a normal Gunicorn process, not serverless functions.
5. Save this as `DATABASE_URL` for the next step. (The app rewrites
   `postgresql://` to `postgresql+psycopg://` automatically.)

> Alternative: Render's own PostgreSQL works too, but the free Render database
> is **deleted after ~30 days**. Neon is recommended for a long-lived demo.

### 2.2 Deploy the backend on Render

1. Push this repository to GitHub first (Render deploys from Git).
2. Go to <https://dashboard.render.com> → **New** → **Blueprint**.
3. Connect the repository `ramdas-5/ReTurn` (or your fork).
4. Render reads `render.yaml`. Confirm:
   - Service `return-api`, Docker, **Free** plan, region **Singapore**.
   - `DATABASE_URL` → paste the Neon URL from step 2.1.
   - `CORS_ALLOWED_ORIGINS` → leave blank for now (or your future Vercel URL).
   - `FLASK_SECRET_KEY` is generated automatically.
5. Click **Apply / Create**. The first build takes ~5–10 minutes.
6. Wait for the log lines:
   ```text
   Running database migrations…
   …
   Starting ReTurn API on 0.0.0.0:<port>…
   Booting worker with pid: …
   ```
7. Copy the public URL, e.g. `https://return-api-xxxx.onrender.com`.
8. Open `https://return-api-xxxx.onrender.com/api/v1/health`. Expected:
   ```json
   {"data":{"status":"ok","database":"postgresql",…}}
   ```

> **Manual verification:** if the health response says `"status":"degraded"`,
> the `DATABASE_URL` is wrong. Fix it in **Environment** and redeploy.

### 2.3 Deploy the frontend on Vercel

1. Go to <https://vercel.com/new> → import the same GitHub repository.
2. **Root Directory** → click **Edit** → select **`frontend`**. (Critical.)
3. Framework preset → **Next.js** (auto-detected after the root is set).
4. Build & Output Settings → leave defaults (`npm run build`, `.next`).
5. Before clicking Deploy, open **Environment Variables** and add both, for
   **Production, Preview and Development**:
   | Name | Value | Needed at |
   |---|---|---|
   | `FLASK_API_URL` | `https://return-api-xxxx.onrender.com` | build time (rewrites) |
   | `API_INTERNAL_URL` | `https://return-api-xxxx.onrender.com` | runtime (server components) |
6. Click **Deploy**. First build ~2–4 minutes.
7. Open the Vercel URL. The landing page must load.

> **Why both variables?** `FLASK_API_URL` is baked into the Next rewrite during
> `next build`. `API_INTERNAL_URL` is read by server components at request time.
> If you change the backend URL later, you must **redeploy** (not just restart)
> so the rewrite is rebuilt.

### 2.4 (Recommended) Lock CORS to your Vercel domain

In Render → `return-api` → **Environment**, set:

```text
CORS_ALLOWED_ORIGINS=https://your-project.vercel.app
```

This is only a defence-in-depth header. The browser never calls Render
directly, but this prevents other sites from using the API with credentials.
Click **Save Changes** (Render redeploys automatically).

### 2.5 Warm up the free backend before any demo

Render free services **sleep after ~15 minutes of inactivity**. The first
request then takes 30–60 seconds, which can exceed Vercel's proxy timeout.

- Before showing the app (and before judging), open
  `https://return-api-xxxx.onrender.com/api/v1/health` in a browser and wait
  until it returns `{"status":"ok"…}`.
- Optional: create a free monitor at <https://cron-job.org> that GETs that URL
  every 10 minutes so the API stays awake.

---

## 3. Post-deploy verification (5 minutes)

Do this in order; each step proves one layer.

1. **API direct:** `GET https://return-api-xxxx.onrender.com/api/v1/health` → 200, `"status":"ok"`.
2. **Proxy:** `GET https://your-project.vercel.app/api/v1/health` → same JSON.
   This proves the rewrite target is correct.
3. **Cookie bootstrap:** open
   `https://your-project.vercel.app/api/v1/auth/csrf`; confirm a `rt_csrf`
   cookie appears in DevTools → Application → Cookies for the Vercel domain.
4. **Login:** go to `/auth` and sign in as `admin@return.demo` /
   `ReTurn#2026`; you should land on `/admin`.
5. **Server component auth:** reload `/admin`; it should render the overview
   (not redirect to `/auth`). This proves `API_INTERNAL_URL` + forwarded cookies.
6. **Matching:** `/admin/batches` → **Find compatible requests** → inspect the
   feasible group and counterexamples.
7. **Partner flow:** sign in as `partner@return.demo`, accept/start a route,
   update a parcel.
8. **Customer privacy:** sign in as `rahul@return.demo`; verify only that
   customer's data is visible.

---

## 4. Environment variable reference (backend)

| Variable | Production value | Notes |
|---|---|---|
| `DATABASE_URL` | Neon direct URL with `?sslmode=require` | `postgresql://` is auto-converted |
| `FLASK_SECRET_KEY` | long random string | Auto-generated by `render.yaml` |
| `FLASK_ENV` | `production` | Also turns `Secure` cookies on by default |
| `SESSION_COOKIE_SECURE` | `true` | Required for HTTPS cookies |
| `TRUST_PROXY_HEADERS` | `true` | One proxy hop (Render) |
| `CORS_ALLOWED_ORIGINS` | `https://your-project.vercel.app` | Optional, defence-in-depth |
| `RATE_LIMIT_ENABLED` | `true` | In-memory, per worker |
| `ROUTING_PROVIDER` | `auto` | Falls back to labelled estimates |
| `OSRM_BASE_URL` | `https://router.project-osrm.org` | Public OSRM |
| `ROUTING_TIMEOUT_SECONDS` | `2` | Lower keeps requests under proxy limits |
| `SEED_DEMO_DATA` | `true` for the demo | Seeds only when no users exist |
| `SEED_DEMO_DATA_RESET` | `false` | `true` wipes data on every start |
| `GUNICORN_WORKERS` | `1` | Fits the 512 MB free instance |
| `GUNICORN_THREADS` | `4` | Handles concurrent requests |
| `SESSION_TTL_HOURS` | `24` | Session lifetime |

Frontend (Vercel):

| Variable | Value | Scope |
|---|---|---|
| `FLASK_API_URL` | `https://return-api-xxxx.onrender.com` | build + runtime |
| `API_INTERNAL_URL` | `https://return-api-xxxx.onrender.com` | runtime |

Never prefix any of these with `NEXT_PUBLIC_`.

---

## 5. Seed data and demo accounts

`render.yaml` sets `SEED_DEMO_DATA=true`, so the first boot creates the
fictional demo scenario and the accounts documented in the README
(password `ReTurn#2026`). On later boots `seed-if-empty` sees existing users
and **skips** seeding, so user-created data is not wiped.

To reset the demo intentionally:

```bash
# Render Dashboard → return-api → Shell
python manage.py seed
```

To switch to a real (non-demo) deployment:

1. Set `SEED_DEMO_DATA=false` in Render.
2. Remove the seeded accounts:
   ```sql
   -- Neon SQL editor, review before running
   DELETE FROM users WHERE email LIKE '%@return.demo';
   ```
   (Delete dependent rows first, or recreate the database, if foreign keys
   block this.)
3. Change all real credentials and re-run `/auth` registration.

> Demo accounts are public knowledge. Never leave seeding enabled on a
> deployment that stores real personal data.

---

## 6. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Vercel page shows “The ReTurn API could not be reached” | `FLASK_API_URL` missing/wrong at build time | Set it, then **Redeploy** |
| `/api/v1/health` through Vercel returns 404/500 | Rewrite target has a trailing slash or `http://localhost` | Use the full `https://…onrender.com` URL, no trailing slash |
| Login succeeds but `/admin` bounces to `/auth` | `API_INTERNAL_URL` missing at runtime, or cookie not `Secure` | Set `API_INTERNAL_URL`; ensure `SESSION_COOKIE_SECURE=true` and you use HTTPS |
| `csrf_failed` on POST | `rt_csrf` cookie blocked/expired | Reload, sign in again; confirm cookies are first-party on the Vercel domain |
| Render health check fails | Migrations failed / DB unreachable | Read Render logs; check `DATABASE_URL` and `sslmode=require` |
| First request takes ~1 minute | Render free service asleep | Warm up `/api/v1/health` before use |
| Matching preview times out | Public OSRM slow, several matrix calls | Set `ROUTING_PROVIDER=estimated` (still honest, labelled estimates) or lower `ROUTING_TIMEOUT_SECONDS` |
| `ModuleNotFoundError` / huge image | Local files copied into Docker | Ensure `backend/.dockerignore` is committed |

---

## 7. Security hardening checklist before sharing the link

- [ ] `FLASK_SECRET_KEY` is random and not the `.env.example` value.
- [ ] `SESSION_COOKIE_SECURE=true` and the site is served over HTTPS.
- [ ] `SEED_DEMO_DATA` decision is intentional.
- [ ] `CORS_ALLOWED_ORIGINS` contains only your domain(s).
- [ ] Neon database password is stored only in Render env vars, never in Git.
- [ ] `.env` is not committed (`git ls-files | grep env` must not list it).
- [ ] Demo credentials are removed before real data is stored.

---

## 8. Known limitations of the free deployment

- Render free web services sleep; Neon free compute can suspend after idle.
- The rate limiter is **in-process**: with `GUNICORN_WORKERS=1` it is
  consistent, but it is not shared across instances.
- Public OSRM is best-effort. The app degrades to explicitly labelled estimates.
- Vercel Hobby functions/proxy have execution limits; keep matching groups small
  (default `MATCHING_MAX_GROUP_SIZE=3`).
- No email delivery, MFA or payment integration (unchanged from local).
- Uploads are not implemented, so no object storage is required.

---

## 9. Optional: self-hosting everything with Docker

The existing Compose file still works for a single VM:

```bash
cp .env.example .env
# edit FLASK_SECRET_KEY, SESSION_COOKIE_SECURE=true, and the public URLs
docker compose up --build -d
```

Put Nginx/Caddy in front for TLS, set `TRUST_PROXY_HEADERS=true`, and point
DNS at the VM. In that setup set `FLASK_API_URL` to the public API origin and
rebuild the frontend image.
