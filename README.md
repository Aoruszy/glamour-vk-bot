# Glamour

Glamour is an MVP CRM platform for a beauty salon built around a VK bot, a FastAPI backend, and a React admin dashboard.

## Workspace Layout

```text
backend/   FastAPI service, CRM logic, seed script
frontend/  React admin dashboard
docs/      Architecture notes
```

## MVP Features

- client CRM with VK ID registration
- services and categories management
- masters management with assigned services
- schedules by master and day
- appointment creation, cancellation, rescheduling, and history
- admin-side status updates for appointments
- available slot calculation with double-booking protection
- notification queue for confirmations and reminders
- summary statistics for the admin side
- VK callback endpoint with a stateful booking flow
- optional real outbound VK replies through `messages.send`
- React dashboard for daily operations
- admin authentication for the CRM dashboard and protected API routes

## Run Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -e .
python -m app.scripts.seed_demo --reset
uvicorn app.main:app --reload
```

Backend URLs:

- API: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`

## Run Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend URL:

- Admin dashboard: `http://127.0.0.1:5173`

If you build the frontend with `npm run build`, FastAPI will also serve it from `http://127.0.0.1:8000/admin`.

Default admin credentials:

- username: `admin`
- password: `glamour-admin`

These values can be changed through backend environment variables.

To enable real VK replies, set `VK_ACCESS_TOKEN` and keep the callback secret and confirmation token aligned with your VK group settings.

Additional salon info for the bot can be configured through:

- `SALON_NAME`
- `SALON_ADDRESS`
- `SALON_PHONE`
- `SALON_WORKING_HOURS`
- `SALON_MAP_URL`
- `SALON_WEBSITE_URL`

## Run With Docker

```bash
docker compose up --build -d
docker compose run --rm app python -m app.scripts.seed_demo --reset
```

Docker URLs:

- App with embedded admin dashboard: `http://127.0.0.1:8000/admin`
- API docs: `http://127.0.0.1:8000/docs`
- PostgreSQL: `localhost:5432`

## Production Deployment

The project is ready for cloud deployment with HTTPS and a reverse proxy.

Quick start:

```bash
cp .env.production.example .env.production
docker compose --env-file .env.production -f docker-compose.production.yml up --build -d
docker compose --env-file .env.production -f docker-compose.production.yml exec app python -m app.scripts.seed_demo --reset
```

Production stack:

- `app` - FastAPI backend with embedded admin dashboard
- `postgres` - PostgreSQL database
- `caddy` - HTTPS reverse proxy with automatic certificates

Important production URLs after setup:

- admin dashboard: `https://your-domain/admin`
- VK callback endpoint: `https://your-domain/api/v1/vk/events`
- healthcheck: `https://your-domain/healthz`

Detailed server setup is described in `docs/deployment.md`.

For a shared Ubuntu server without Docker, where another project is already running, use `docs/deployment-ubuntu-shared.md`.

## Main API Areas

- `/api/v1/clients`
- `/api/v1/service-categories`
- `/api/v1/services`
- `/api/v1/masters`
- `/api/v1/schedules`
- `/api/v1/appointments`
- `/api/v1/notifications`
- `/api/v1/stats/summary`
- `/api/v1/vk/events`

## Demo Data

Use `python -m app.scripts.seed_demo --reset` inside `backend` to create demo categories, services, masters, clients, schedules, and appointments for the MVP presentation.

## Notification Queue

Pending notifications can be processed in two ways:

- from the admin dashboard with the `Process queue` button
- manually from the backend with `python -m app.scripts.process_notifications`

## Tests

```bash
cd backend
pip install -e .[dev]
pytest
```
