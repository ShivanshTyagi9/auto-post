# OpenInstaFlow — Instagram automation as a service

OpenInstaFlow is a multi-tenant backend you run **once, yourself**, and then resell to
customers who each connect their own Instagram Business/Creator account. Each customer gets
their own login, their own posts, and their own AI-powered "autopilot" that plans and
captions content for them — they don't touch a CLI, an MCP client, or any code.

You (the operator) manage everything from an admin dashboard: generate activation codes,
onboard customers, and watch posts/activity across every account from one place.

## What's in the box

| Piece | File(s) | What it does |
|---|---|---|
| REST API | `src/openinstaflow/api.py` | FastAPI backend — admin + customer endpoints |
| Auth | `src/openinstaflow/supabase_auth.py` | Supabase Auth — admin/customer signup & login, session tokens |
| Database | `src/openinstaflow/database.py` | Supabase Postgres (via SQLAlchemy) — customers, posts, media queue, autopilot settings |
| Scheduler | `src/openinstaflow/multi_scheduler.py` | Persistent post scheduler (APScheduler) — survives restarts |
| AI captions | `src/openinstaflow/ai_caption.py` | OpenAI vision — writes a caption grounded in the actual image |
| Growth agent | `src/openinstaflow/growth_agent.py` | Figures out best posting times/audience and plans the next post |
| Media queue | `src/openinstaflow/media_store.py` | Stores customer-uploaded images/videos for autopilot to use |
| Dashboard | `dashboard/` | Static admin + customer web UI, served by the API |
| MCP server | `src/openinstaflow/tools.py`, `__main__.py` | Optional — same Instagram tools exposed to an MCP client like Claude. Not needed for the SaaS flow below. |

---

## 1. Running it locally

**Prerequisites:** Python 3.10+ (3.11 recommended), pip.

```bash
pip install -e .
cp .env.example .env
```

Create a [Supabase](https://supabase.com) project (free tier is fine), then from
**Project Settings** grab: the **Project URL** (API page), the **anon** and **service_role**
keys (API page), and the Postgres **connection string** (Database page → Connection string →
URI — note the `[YOUR-PASSWORD]` placeholder needs your actual DB password, URL-encoded if it
contains special characters like `@`).

Open `.env` and set, at minimum:

```ini
OPENAI_API_KEY=sk-...        # required for AI captions / the growth agent
PUBLIC_BASE_URL=http://localhost:8000   # see "Going to production" below
SUPABASE_URL=https://xxxxxxxxxxxx.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
DATABASE_URL=postgresql://postgres:your-url-encoded-password@db.xxxxxxxxxxxx.supabase.co:5432/postgres
```

`ENCRYPTION_KEY` auto-generates on first run if left blank, but the server prints it to the
console — **copy it into `.env`** or every restart makes stored Instagram tokens undecryptable.

Start the server:

```bash
python -m openinstaflow.api
```

Open `http://localhost:8000` in a browser. There's no default admin account anymore — create
the first one with a one-time call (only works while zero admins exist; refuses after that, so
it can't be used to self-promote later):

```bash
curl -X POST http://localhost:8000/api/auth/admin/bootstrap \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "choose-a-strong-password"}'
```

Then log in to the dashboard with that email/password.

---

## 2. Operator workflow (you)

1. **Log in to the dashboard** as admin.
2. **Generate activation codes** (Dashboard → Activation Codes → Generate). Each code is a
   one-time signup voucher — this is how you control who can create an account, since there's
   no public signup otherwise.
3. **Send a code to a customer** along with a link to your dashboard. They sign up themselves
   with email + password + that code.
4. From the **Customers** page you can see every customer's connection status, test their
   Instagram token, and view their post history. (The API also supports publishing/scheduling
   on a customer's behalf as admin — `POST /api/customers/{id}/publish` — but there's no
   dashboard button for it yet.)
5. **Activity log** and **Posts** pages give you a live feed across all customers — useful for
   support ("why didn't my post go out?") without needing database access.

---

## 3. What a customer needs from Instagram (step-by-step)

This is the part customers usually get stuck on. Walk them through it once — after the token
is in place, they never touch Meta's developer tools again.

**Step 1 — Convert to a Business or Creator account.**
In the Instagram app: Settings → Account type and tools → Switch to professional account →
Business (or Creator). A personal account cannot use the API at all.

**Step 2 — Create a Meta developer app.**
At `developers.facebook.com`, create an app (type: "Business"), and add the
**Instagram Graph API** / **Instagram API with Instagram Login** product to it. This is a
one-time setup per app — you can reuse the same app for all your customers, you don't need
one app per customer.

**Step 3 — Generate an access token for their account.**
Using Meta's Graph API Explorer (or your app's own login flow), the customer authorizes your
app against their Instagram account and grants these permissions:
- `instagram_business_basic`
- `instagram_business_content_publish`
- `instagram_business_manage_insights` (needed for the growth agent's "best time to post" analysis)
- `instagram_business_manage_messages` (only if you want DM tools)

This produces a **short-lived token** (~1 hour). Exchange it for a **long-lived token**
(~60 days) using Meta's token-exchange endpoint — the long-lived one is what you store.
Long-lived tokens can be refreshed before they expire by calling the same exchange endpoint
again; OpenInstaFlow doesn't currently automate this refresh, so plan to re-collect the token
every couple of months (or build a reminder into your onboarding).

**Step 4 — Find their Instagram user/business account ID.**
A call to the Graph API's `me` endpoint with that token returns the account's numeric ID
(this is `ig_user_id` everywhere in this app — different from the `@username`).

**Step 5 — Enter the credentials into OpenInstaFlow.**
The customer (or you, on their behalf) opens **Settings** in the customer dashboard and fills in:

| Field | Value |
|---|---|
| `ig_user_id` | the numeric ID from Step 4 |
| `ig_access_token` | the long-lived token from Step 3 |
| `login_kind` | `ig_login` (the default — no Facebook Page required) |

Then click **Test Connection** (`POST /api/me/test-token`) — it pulls the live profile to
confirm the token actually works, and caches the username.

> **Using Facebook Login instead?** If you need Facebook Page management or DM tools, use
> `login_kind=fb_login` instead, which requires the Instagram account to be linked to a
> Facebook Page, and the customer to grant `pages_show_list` + `pages_read_engagement` +
> `instagram_basic` + `instagram_content_publish` + `instagram_manage_messages`. This is the
> older/legacy path — prefer `ig_login` unless you specifically need Pages or DMs.

Once the connection test passes, the customer is ready to publish.

---

## 4. Customer workflow (day-to-day)

**Manual posting — already in the dashboard UI.** From the customer's **Dashboard → Publish**
form: paste an image/video URL (public HTTPS, or a Google Drive share link — those are
auto-converted) or a local file path, write a caption, and publish now or schedule for later.

**Autopilot, the media queue, AI captions, and draft review — backend/API only for now.**
This pass deliberately focused on the backend (per the brief that started this build); the
dashboard doesn't have screens for these yet, so today they're used via direct API calls
(`curl`, Postman, or your own admin tooling) using the customer's JWT from login. Building the
matching dashboard UI is the natural next step — happy to do that next if you want it.

What exists right now, callable as `Authorization: Bearer <customer JWT>`:

```bash
# Let AI write the caption for a manual publish/schedule (no UI checkbox yet — pass the flag directly)
curl -X POST $HOST/api/me/publish -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"image_url": "https://...", "auto_caption": true}'

# Configure autopilot
curl -X PUT $HOST/api/me/autopilot -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"enabled": true, "auto_publish": false, "niche": "artisan coffee shop", "tone": "warm and friendly", "goal": "engagement", "target_location": "Mumbai, India", "timezone": "Asia/Kolkata", "posts_per_week": 3}'

# Upload media into the queue (multipart form)
curl -X POST $HOST/api/me/media -H "Authorization: Bearer $TOKEN" \
  -F "file=@photo.jpg" -F "caption_hint=Fresh espresso shot at the counter"

# Ask the growth agent to plan the next post right now (otherwise it runs automatically every 6h)
curl -X POST $HOST/api/me/autopilot/run-now -H "Authorization: Bearer $TOKEN"

# Review/approve/reject drafts
curl $HOST/api/me/posts?status=draft -H "Authorization: Bearer $TOKEN"
curl -X POST $HOST/api/me/posts/<id>/approve -H "Authorization: Bearer $TOKEN" -d '{}'
curl -X DELETE $HOST/api/me/posts/<id> -H "Authorization: Bearer $TOKEN"   # reject a draft

# Latest growth-agent analysis (best times, audience location)
curl $HOST/api/me/strategy -H "Authorization: Bearer $TOKEN"
```

How autopilot behaves once enabled: every 6 hours the growth agent checks whether a new post
is due (based on `posts_per_week`), and if so it picks the next unused photo/video from the
queue, writes a caption grounded in the actual image plus the niche/tone/goal/location, and
picks a posting time based on when this account's past posts performed best — falling back to
the customer's stated target location/timezone if Instagram won't share audience data (common
for newer or smaller accounts). It either publishes directly (`auto_publish: true`) or saves a
**draft** for the customer/operator to review, edit, and approve.

---

## 5. Deploying this as a service

### Docker (recommended)

```bash
docker compose up -d --build
```

This builds the image and reads `.env`. Make sure `.env` is filled in (especially the
`SUPABASE_*` vars, `DATABASE_URL`, `ENCRYPTION_KEY`, `OPENAI_API_KEY`) *before* the first run —
those keys must stay stable across restarts.

### Required production settings

| Variable | Why it matters in production |
|---|---|
| `PUBLIC_BASE_URL` | **Must be a real, internet-reachable HTTPS URL** (your real domain). Customer-uploaded media is served from `{PUBLIC_BASE_URL}/uploads/...`, and both Instagram and OpenAI's vision API fetch it by that URL — `localhost` will fail silently (the caption falls back to the customer's text hint, and Instagram publish will error). |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` | Auth (admin + customer signup/login) goes through this Supabase project. `service_role` is a secret — server-side only. |
| `DATABASE_URL` | Supabase Postgres connection string. All customers, posts, activation codes, etc. live here — this is what makes the service safe to redeploy without losing data (see below). |
| `ENCRYPTION_KEY` | Encrypts stored Instagram tokens at rest. **Losing this means every customer has to reconnect their Instagram account** — back it up somewhere safe. |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | Powers caption generation and the growth agent. |

### Networking checklist

- Put the server behind HTTPS (a reverse proxy like Caddy/nginx, or your platform's built-in
  TLS — Railway/Render/Fly all do this automatically). Instagram and OpenAI both require HTTPS
  for media URLs in practice.
- `GET /health` is an unauthenticated liveness endpoint — point your platform's health check
  or load balancer at it (not the dashboard API endpoints, which require auth).

### Render / Railway: data persistence

**Both platforms run an ephemeral filesystem by default** — anything written to local disk is
wiped on every redeploy (and on Render, even on a plain restart). Since auth and all structured
data (customers, admins, activation codes, posts, autopilot settings, activity log) now live in
Supabase Postgres rather than a local SQLite file, **none of that is affected by the app
container's disk being wiped** — Supabase persists independently of your Render/Railway
instance, with its own backups.

One thing *isn't* covered by this: **customer-uploaded media files** (`data/uploads/`, written
by `media_store.py` for the autopilot queue) are still plain files on local disk. If you use the
media-queue/autopilot upload feature in production, either:
- attach a persistent disk (Render: Service → **Disks**; Railway: Service → **Volumes**) mounted
  at `/app/data`, or
- skip it for now if customers only publish via direct image/video URLs (no local upload), which
  doesn't touch this path at all.

Set `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, and
`ENCRYPTION_KEY` as real environment variables in the platform's dashboard, not just in a local
`.env` (which isn't deployed). Never rotate `ENCRYPTION_KEY` after the fact — that makes every
already-stored Instagram token undecryptable, forcing every customer to reconnect.

### Onboarding customers once it's live

1. Generate an activation code per customer (or a batch up front) from the admin dashboard.
2. Send them your dashboard URL + their code.
3. Walk them through **Section 3** above (Instagram setup) once — most of the friction is
   getting the long-lived access token, everything after that is point-and-click.

---

## 6. Troubleshooting

- **"Unexpected token... is not valid JSON" in the dashboard** — this means the backend
  returned a raw error page instead of JSON, almost always an unhandled server exception.
  Check the server logs (`docker compose logs -f` or the terminal running
  `python -m openinstaflow.api`) for the actual traceback.
- **Posts fail with "image format not supported"** — the media URL isn't a direct,
  fetchable file. Google Drive *share* links (`drive.google.com/file/d/.../view`) are
  auto-converted to direct download links; if you're hosting media elsewhere, make sure the
  URL points straight at the file, not an HTML viewer page.
- **AI captions silently fall back to the customer's text hint** — check that
  `PUBLIC_BASE_URL` is a real, internet-reachable address (see above) and that
  `OPENAI_API_KEY` is set; failures are logged to the customer's Activity log as
  `ai_caption_failed` with the underlying error.
- **Autopilot says "no post planned"** — either the media queue is empty, autopilot isn't
  due yet based on posts-per-week, or autopilot isn't enabled. Check Settings → Autopilot
  and the Activity log for `autopilot_no_media`.

## Development

```bash
pip install -e .                    # install in dev mode
python -m openinstaflow.api         # run the SaaS backend
python -m openinstaflow             # (optional) run the MCP server on stdio instead
```

## License

MIT
