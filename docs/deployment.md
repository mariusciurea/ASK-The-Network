# Deployment

Two Railway services from this one repository, plus the MySQL plugin:

```
MySQL (Railway plugin)
   ^
   | private network
backend  service  (FastAPI + ADK)   <-- frontend calls it
   ^
   | private network
frontend service  (Streamlit)       <-- public URL, the only one users open
```

## How the build context works here

Both services set a **Root Directory** (`/frontend` and `/backend`), and that
directory *is* the build context. Its root holds `requirements.txt`, `main.py`,
`ui/` - nothing from above it exists in the context:

```
frontend/            <- context root, this is "."
  requirements.txt   <- COPY requirements.txt .      works
  main.py
  ui/
```

So the Dockerfiles use paths relative to their own directory. A repository-root
path fails the build before anything is installed:

```
[ERRO] [3/6] COPY frontend/requirements.txt ./frontend/requirements.txt
failed to compute cache key: "/frontend": not found
```

The same applies to `.dockerignore`: BuildKit reads it from the context root,
which is why there is one in `backend/` and one in `frontend/`, not at the
repository root. `docker-compose.yaml` builds each image from the same
directory, so local builds and Railway behave identically.

If a build ever fails on the very first `COPY`, check the Root Directory
setting before touching the Dockerfile - the two have to agree.

## Service settings

| Setting | frontend | backend |
|---|---|---|
| Root Directory | `/frontend` | `/backend` |
| Dockerfile Path | `/frontend/Dockerfile` | `/backend/Dockerfile` |
| Healthcheck path | `/_stcore/health` | `/health` |
| Config as code | `railway.json` (inside the root directory) | `railway.json` (inside the root directory) |

These are the settings the project already uses - the Dockerfiles are written
for them, so nothing has to change in the dashboard.

Railway injects `PORT`; both images bind `0.0.0.0:$PORT`.

## Environment variables

### backend

| Variable | Value | Why |
|---|---|---|
| `DB_URL` | `mysql+pymysql://root:${{MySQL.MYSQL_ROOT_PASSWORD}}@${{MySQL.RAILWAY_PRIVATE_DOMAIN}}:3306/railway` | Ticket database |
| `SESSION_SERVICE_URI` | same as `DB_URL` | Otherwise conversations live in a SQLite file that is wiped on every deploy |
| `GOOGLE_API_KEY` | your key | The agent cannot answer without it |
| `JWT_SECRET_KEY` | 32+ random characters | Anyone who can read this repo could otherwise forge a token |
| `ENVIRONMENT` | `production` | Turns on the startup check for unsafe defaults |
| `ENABLE_DEV_UI` | `false` | The ADK dev UI has no authentication of its own |
| `ALLOWED_ORIGINS` | the frontend's public URL | Replaces the `*` CORS policy |

Generate the secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

### frontend

| Variable | Value | Why |
|---|---|---|
| `BASE_URL` | `http://<backend-service>.railway.internal:8082` | Private networking: no public hop, no egress cost |
| `AGENT_TIMEOUT_SECONDS` | `180` (default) | An agent turn with tools and charts is slow |

If you use the backend's public URL instead, use `https://` and keep in mind
that the ADK endpoints are now authenticated - which is the point.

## First deploy

1. Push to `master`; both services build from the same commit.
2. Create the tables and load the seed data once:
   ```bash
   railway run --service backend python -m backend.scripts.initialize_db
   ```
   Add `--force` only when you want the tickets deleted and reloaded from the CSV.
3. Open the frontend URL, register an account, accept the terms.

## Security notes

* Every ADK endpoint now requires a bearer token, and the token's identity must
  match the `userId` in the URL or in the body of `/run`. Before this change
  anyone could list and read another user's sessions and artifacts.
* `ENVIRONMENT=production` refuses to start with the default JWT secret, with a
  secret under 32 characters, with the local database URL, or with the dev UI
  enabled.
* Both images run as a non-root user.
* Secrets belong in Railway variables, never in `settings.py`. The defaults in
  the code exist only so the app runs locally out of the box.

## Scaling

The backend runs a single uvicorn worker on purpose. The agent is I/O bound, so
one worker handles concurrent users, but the ADK artifact store is local to the
container: a second worker or replica would not see artifacts written by the
first. Before raising `WEB_CONCURRENCY` or `numReplicas`, move artifacts to a
shared store (GCS) - sessions already move to MySQL with `SESSION_SERVICE_URI`.

## Local run

```bash
docker compose up --build
docker compose run --rm backend python -m backend.scripts.initialize_db
# frontend: http://localhost:8501
```
