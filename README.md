# Milan — matrimony platform prototype

A members-only matrimony site: people sign up, confirm their email, and build a
profile with multiple photos. Nothing at all is visible to guests. A small staff
screen lets an administrator view every account and deactivate anyone.

Built with **Django 6** and server-rendered templates. No frontend build step —
one hand-written stylesheet and a few dozen lines of vanilla JavaScript, so the
whole thing runs from a single `manage.py runserver`.

---

## What is in it

**Accounts**
- Sign-up with email + password (email is the username; case-insensitive).
- Email verification through a signed, self-expiring link — no token table to
  clean up. A link stops working if the address on the account changes.
- Unverified accounts cannot sign in; they are offered a "resend link" instead.
- Password reset over email.
- Site-wide login gate: every URL requires a signed-in member unless it is on an
  explicit public allow-list, so a new page cannot leak content by accident.

**Profiles**
- One profile per member: name, date of birth, gender, height, marital status,
  religion/community, mother tongue, city, country, education, occupation and a
  free-text "about me".
- Multi-photo upload, drag-and-drop or file picker, several files at once.
  Every upload is re-encoded server-side: rotated upright from its EXIF flag,
  resized to fit 1600 px, stripped of metadata (including GPS) and saved as a
  progressive JPEG.
- Pick which photo leads the profile; delete photos; the "main" slot is
  re-elected automatically if you delete the current one.
- A profile only appears in the members list once name, date of birth, gender
  and city are filled in — nobody browses empty cards.
- Under-18 sign-ups are rejected at the form.

**Admin**
- `/manage/members/` — a compact staff screen: counts, search, status filter and
  a one-click deactivate/reactivate per account. Superusers cannot be
  deactivated from here.
- `/admin/` — the full Django admin, with photo thumbnails inline on profiles
  and bulk activate/deactivate actions.

**Design**
- Responsive from 320 px up; verified at 360 / 390 / 412 / 430 / 720 / 1280 px.
- Light and dark palettes are both defined, so phone "auto dark mode" does not
  repaint the site with its own guessed colours.
- Respects `prefers-reduced-motion`.

---

## Running it locally

Requires Python 3.11+.

```bash
git clone <this repository>
cd milan-matrimony

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # optional; sensible defaults without it

python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Open <http://127.0.0.1:8000/>. You will be sent to the login page — that is the
point of the site.

With no `EMAIL_HOST` configured, verification emails are **printed to the
terminal** instead of being sent. Copy the `/accounts/verify/...` link out of the
console and paste it into the browser to confirm a test account.

### Demo data

```bash
python manage.py seed_demo
```

Creates 12 ready-made members, each with three generated photos (gradient
monograms drawn locally — no stock imagery). They are all verified and share the
password `demo1234`. Running it again does nothing to existing accounts.

### Tests

```bash
python manage.py test
```

32 tests covering sign-up, verification (valid / tampered / expired / stale
address), the guest lock-out, profile publishing rules, photo processing, the
per-profile photo limit, ownership checks on delete, and the admin screen.

---

## Configuration

Everything environment-specific is read from the environment; see
`.env.example` for the annotated list. The ones that matter in production:

| Variable | Why it matters |
| --- | --- |
| `SECRET_KEY` | Signs sessions **and verification links**. Changing it invalidates outstanding links. |
| `DEBUG` | Must be `0` in production; turns on HSTS, secure cookies and SSL redirect. |
| `ALLOWED_HOSTS` | Comma-separated hostnames. |
| `CSRF_TRUSTED_ORIGINS` | Your `https://` origin, once behind a domain. |
| `SITE_BASE_URL` | Public base URL used to build links inside emails. Get this wrong and verification links point at the wrong host. |
| `DATABASE_URL` | Leave unset for SQLite; set for PostgreSQL. |
| `EMAIL_HOST` … | SMTP details. Unset ⇒ console output. |
| `SITE_NAME`, `SITE_TAGLINE` | Re-brand the whole site without touching code. |
| `MEDIA_ROOT` | Where uploaded photos live. Point this at persistent storage. |

---

## Deploying

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
```

Static files are served by WhiteNoise, so no separate static-file server is
needed. Two things do need attention:

1. **Uploads.** `MEDIA_ROOT` must be on storage that survives a redeploy — a
   mounted disk, or S3-compatible object storage. On an ephemeral filesystem
   (Heroku-style dynos, some free tiers) uploaded photos vanish on restart.
2. **Email.** Verification is the front door of the site, so use a real SMTP
   provider (Brevo, SendGrid, Mailgun, Amazon SES, or Google Workspace) rather
   than a personal Gmail account.

Run it behind nginx or a platform router terminating TLS; the settings already
trust `X-Forwarded-Proto`.

---

## Layout

```
config/         settings, root URLs, WSGI
accounts/       user model, auth backend, login gate, sign-up + verification
profiles/       profile & photo models, image processing, member views, admin screen
  management/commands/seed_demo.py
templates/      base layout, auth pages, profile pages, email bodies
static/css/     one stylesheet; all colours are CSS custom properties at the top
```

Notable design decisions, in case they come up later:

- `is_active` means "an administrator switched this account off";
  `email_verified_at` means "the address was confirmed". Keeping them apart is
  what lets the login page tell a deactivated account from an unconfirmed one.
- Verification links are signed values, not database rows — nothing to expire by
  cron, and a link is scoped to the address it was sent to.
- Photos are re-encoded on upload rather than served as-is; that is what keeps
  a 12 MB phone photo (with GPS in its EXIF) from ever reaching the disk.
- The login gate is a middleware allow-list rather than a decorator per view,
  because "no guest access" is safer as a default than as something you must
  remember to add.

---

## Not included (deliberately out of scope for this prototype)

Search and filtering, messaging or interest requests, partner preferences,
horoscope matching, paid plans, photo moderation queue, and profile privacy
levels. The models leave room for all of them; none are built.
