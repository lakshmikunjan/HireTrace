# HireTrace

Automatically track job applications by parsing Gmail confirmation emails.
No spreadsheets. No manual entry.

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12 + FastAPI |
| Database | PostgreSQL 16 |
| Worker | Celery + Redis |
| Email | Gmail API (read-only OAuth2) |
| Parser | Regex-first → Claude claude-haiku-4-5 fallback |
| Frontend | React 18 + Vite + Tailwind CSS |

---

## Prerequisites

- Docker + Docker Compose
- A [Google Cloud Console](https://console.cloud.google.com) project with the Gmail API enabled
- An [Anthropic API key](https://console.anthropic.com) (only used as LLM fallback for ambiguous emails)

---

## Setup

### 1. Clone and configure

```bash
git clone <repo-url>
cd HireTrace
cp backend/.env.example backend/.env
```

Edit `backend/.env` and fill in:

```env
GOOGLE_CLIENT_ID=<your-google-client-id>
GOOGLE_CLIENT_SECRET=<your-google-client-secret>
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/callback
ANTHROPIC_API_KEY=<your-anthropic-api-key>
SESSION_SECRET=<any-random-32-char-string>
```

### 2. Google OAuth2 Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com) → **APIs & Services → Credentials**
2. Create an **OAuth 2.0 Client ID** (Web application)
3. Add `http://localhost:8000/auth/callback` as an authorized redirect URI
4. Enable the **Gmail API** under APIs & Services → Library

### 3. Start the full stack

```bash
docker-compose up --build
```

This starts:
- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`
- FastAPI backend on `http://localhost:8000`
- Celery worker (email scanning)
- Celery beat (periodic scheduler)
- React frontend on `http://localhost:5173`

### 4. Run database migrations

```bash
docker-compose exec backend alembic upgrade head
```

### 5. Open the app

Visit `http://localhost:5173` → click **Connect Gmail** → authorize read-only access.

---

## Local Development (without Docker)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in values

# Run migrations
alembic upgrade head

# Start API
uvicorn app.main:app --reload

# Start worker (separate terminal)
celery -A app.worker.celery_app worker --loglevel=info

# Start beat scheduler (separate terminal)
celery -A app.worker.celery_app beat --loglevel=info
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## API Reference

Swagger UI is available at `http://localhost:8000/docs`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/auth/google` | Start Gmail OAuth2 flow |
| GET | `/auth/callback` | OAuth2 callback |
| GET | `/auth/me` | Current user info |
| POST | `/auth/logout` | Revoke tokens + clear session |
| GET | `/applications` | List applications (filterable) |
| PATCH | `/applications/{id}` | Override status manually |
| DELETE | `/applications/{id}` | Delete one application |
| POST | `/applications/scan` | Trigger manual inbox scan |
| DELETE | `/applications/users/me` | Delete account + all data |
| GET | `/dashboard/stats` | Funnel + platform analytics |

### Filter parameters for `GET /applications`

| Param | Type | Example |
|-------|------|---------|
| `platform` | string | `linkedin`, `indeed`, `direct` |
| `status` | string | `applied`, `offer`, `ghosted` |
| `remote_only` | bool | `true` |
| `has_salary` | bool | `true` |

---

## How Parsing Works

1. A Celery Beat task runs every **15 minutes**, querying Gmail for emails matching job application keywords.
2. Each new email (deduplicated by Gmail message ID) is routed to a **platform-specific regex parser** (LinkedIn, Indeed, or generic ATS).
3. If the regex parser's confidence score is **< 0.7**, the email is passed to **Claude claude-haiku-4-5** for structured extraction.
4. The parsed result is stored as a `JobApplication` row.
5. A daily task at 08:00 UTC marks applications with **no activity for 14+ days** as `ghosted`.

---

## Project Structure

```
HireTrace/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Environment settings
│   │   ├── database.py          # SQLAlchemy async engine
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── schemas/             # Pydantic I/O schemas
│   │   ├── routers/             # FastAPI route handlers
│   │   ├── services/
│   │   │   ├── gmail.py         # Gmail API wrapper
│   │   │   ├── email_scanner.py # Scan orchestrator
│   │   │   └── parser/          # Hybrid parsing engine
│   │   └── worker/              # Celery tasks + scheduler
│   └── alembic/                 # Database migrations
└── frontend/
    └── src/
        ├── pages/               # Auth, Dashboard, Settings
        ├── components/          # Table, Chart, Filters, etc.
        ├── hooks/               # React Query hooks
        └── lib/                 # API client + types
```
