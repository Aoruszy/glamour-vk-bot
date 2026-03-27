# Glamour Architecture Notes

## Product Identity

- Product name: `Glamour`
- Domain: beauty salon CRM with a VK bot as the main customer touchpoint
- Delivery target: MVP suitable for a diploma project and further expansion

## Suggested Stack

- Backend: Python + FastAPI
- Database: PostgreSQL
- Queue and reminders: Redis + APScheduler or Celery in a later phase
- Admin UI: React dashboard as a separate module
- VK integration: Callback API or Long Poll handled by the backend

## Current MVP Delivery

- `backend/` contains the FastAPI API, CRM domain model, and demo seed script
- `frontend/` contains the React admin dashboard for appointments and salon operations
- the built frontend can be served by FastAPI from `/admin` for a single-app demo setup
- admin-only CRM routes are protected with a signed access token
- Docker Compose can run the MVP with PostgreSQL as the primary database

## MVP Modules

1. `vk`
   Handles incoming VK events, keyboard flows, and dialog state.
2. `clients`
   Stores customer profiles, VK identity, phone number, and visit history.
3. `services`
   Keeps service categories, prices, durations, and active status.
4. `masters`
   Stores staff profiles, skills, and availability.
5. `appointments`
   Creates, validates, updates, and cancels bookings.
6. `schedules`
   Manages working days and free slots.
7. `notifications`
   Sends confirmations and reminders.
8. `admin`
   Exposes the internal API for the future dashboard.

## Core Domain Entities

- `Client`
- `Master`
- `ServiceCategory`
- `Service`
- `Appointment`
- `Schedule`
- `Notification`
- `AuditLog`

## Current API Surface

- `GET /health`
- `GET /api/v1/meta`
- `GET /api/v1/clients`
- `POST /api/v1/clients`
- `GET /api/v1/service-categories`
- `POST /api/v1/service-categories`
- `POST /api/v1/vk/events`
- `GET /api/v1/services`
- `POST /api/v1/services`
- `GET /api/v1/services`
- `GET /api/v1/masters`
- `POST /api/v1/masters`
- `GET /api/v1/schedules`
- `POST /api/v1/schedules`
- `GET /api/v1/appointments/me`
- `GET /api/v1/appointments/available-slots`
- `POST /api/v1/appointments`
- `POST /api/v1/appointments/{appointment_id}/cancel`
- `POST /api/v1/appointments/{appointment_id}/reschedule`
- `GET /api/v1/notifications`
- `GET /api/v1/stats/summary`

## Non-Functional Goals

- Response time for common requests under 2-3 seconds
- Protection against double booking
- Safe secret storage in environment variables
- Clear module boundaries for future admin panel expansion
