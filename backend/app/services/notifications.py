from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.enums import AppointmentStatus, NotificationStatus, NotificationType
from app.models.appointment import Appointment
from app.models.client import Client
from app.models.master import Master
from app.models.notification import Notification
from app.models.service import Service
from app.services.vk_api import VkApiClient


def _local_timezone() -> ZoneInfo:
    return ZoneInfo(get_settings().app_timezone)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _appointment_start_utc(appointment: Appointment) -> datetime:
    local_dt = datetime.combine(
        appointment.appointment_date,
        appointment.start_time,
        tzinfo=_local_timezone(),
    )
    return local_dt.astimezone(UTC)


def _expected_send_at(notification_type: NotificationType, appointment: Appointment) -> datetime | None:
    start_utc = _appointment_start_utc(appointment)
    if notification_type == NotificationType.REMINDER_24H:
        return start_utc - timedelta(hours=24)
    if notification_type == NotificationType.REMINDER_2H:
        return start_utc - timedelta(hours=2)
    return None


def _appointment_datetime_label(appointment: Appointment) -> str:
    return f"{appointment.appointment_date.strftime('%d.%m.%Y')} в {appointment.start_time.strftime('%H:%M')}"


def _appointment_status_label(status: str) -> str:
    labels = {
        "new": "новая",
        "confirmed": "подтверждена",
        "completed": "завершена",
        "canceled_by_client": "отменена клиентом",
        "canceled_by_admin": "отменена салоном",
        "rescheduled": "перенесена",
        "no_show": "отмечена как неявка",
    }
    return labels.get(status, status)


def refresh_appointment_notifications(
    db: Session,
    appointment: Appointment,
    *,
    include_confirmation: bool = True,
) -> None:
    db.execute(delete(Notification).where(Notification.appointment_id == appointment.id))

    start_dt = _appointment_start_utc(appointment)
    now = _now_utc()
    notifications: list[Notification] = []
    if include_confirmation:
        notifications.append(
            Notification(
                appointment_id=appointment.id,
                type=NotificationType.BOOKING_CONFIRMATION,
                send_at=now,
                status=NotificationStatus.PENDING,
                message="?????? ??????? ? ????????????.",
            )
        )

    reminder_24h_at = _expected_send_at(NotificationType.REMINDER_24H, appointment)
    if reminder_24h_at > now:
        notifications.append(
            Notification(
                appointment_id=appointment.id,
                type=NotificationType.REMINDER_24H,
                send_at=reminder_24h_at,
                status=NotificationStatus.PENDING,
                message="??????????? ? ?????? ?? 24 ????.",
            )
        )

    reminder_2h_at = _expected_send_at(NotificationType.REMINDER_2H, appointment)
    if reminder_2h_at > now:
        notifications.append(
            Notification(
                appointment_id=appointment.id,
                type=NotificationType.REMINDER_2H,
                send_at=reminder_2h_at,
                status=NotificationStatus.PENDING,
                message="??????????? ? ?????? ?? 2 ????.",
            )
        )

    db.add_all(notifications)


def append_status_notification(
    db: Session,
    *,
    appointment_id: int,
    notification_type: NotificationType,
    message: str,
) -> None:
    db.add(
        Notification(
            appointment_id=appointment_id,
            type=notification_type,
            send_at=_now_utc(),
            status=NotificationStatus.PENDING,
            message=message,
        )
    )


def clear_pending_notifications(db: Session, *, appointment_id: int) -> None:
    db.execute(
        delete(Notification).where(
            Notification.appointment_id == appointment_id,
            Notification.status == NotificationStatus.PENDING,
        )
    )


def sync_pending_reminder_schedule(db: Session) -> None:
    notifications = list(
        db.scalars(
            select(Notification).where(
                Notification.status == NotificationStatus.PENDING,
                Notification.type.in_([NotificationType.REMINDER_24H, NotificationType.REMINDER_2H]),
            )
        )
    )
    for notification in notifications:
        appointment = db.get(Appointment, notification.appointment_id)
        if not appointment:
            continue
        expected = _expected_send_at(notification.type, appointment)
        if expected is None:
            continue
        if _as_utc(notification.send_at) != expected:
            notification.send_at = expected
    db.flush()


def _render_notification_message(db: Session, notification: Notification) -> str:
    appointment = db.get(Appointment, notification.appointment_id)
    if not appointment:
        return notification.message or "Запись для уведомления не найдена."

    service = db.get(Service, appointment.service_id)
    master = db.get(Master, appointment.master_id)
    start_label = _appointment_datetime_label(appointment)
    service_name = service.name if service else "услуга"
    master_name = master.full_name if master else "мастер"

    if notification.type == NotificationType.BOOKING_CONFIRMATION:
        return f"Ваша запись подтверждена: {service_name}, мастер {master_name}, {start_label}."
    if notification.type == NotificationType.REMINDER_24H:
        return f"Напоминание: через 24 часа у вас запись на {service_name} к мастеру {master_name}, {start_label}."
    if notification.type == NotificationType.REMINDER_2H:
        return f"Напоминание: через 2 часа у вас запись на {service_name} к мастеру {master_name}, {start_label}."
    if notification.type == NotificationType.CANCELLATION:
        return f"Ваша запись на {service_name}, {start_label}, была отменена."
    if notification.type == NotificationType.RESCHEDULE:
        return f"Ваша запись на {service_name} была перенесена. Новое время: {start_label}."
    if notification.type == NotificationType.STATUS_UPDATE:
        status_label = _appointment_status_label(appointment.status.value)
        return f"Статус вашей записи на {service_name}, {start_label}, обновлен: {status_label}."
    return notification.message or "По вашей записи есть обновление."


def process_due_notifications(db: Session, *, vk_client: VkApiClient | None = None) -> dict[str, int]:
    settings = get_settings()
    sync_pending_reminder_schedule(db)
    now = _now_utc()
    notifications = list(
        db.scalars(
            select(Notification)
            .where(
                Notification.status == NotificationStatus.PENDING,
                Notification.send_at <= now,
            )
            .order_by(Notification.send_at, Notification.id)
        )
    )

    sent = 0
    skipped = 0
    failed = 0

    if vk_client is None and settings.vk_access_token:
        vk_client = VkApiClient(
            access_token=settings.vk_access_token,
            api_version=settings.vk_api_version,
        )

    for notification in notifications:
        appointment = db.get(Appointment, notification.appointment_id)
        client = db.get(Client, appointment.client_id) if appointment else None
        if notification.channel != "vk" or not appointment or not client or not client.vk_user_id:
            notification.status = NotificationStatus.SKIPPED
            skipped += 1
            continue

        if appointment.status in {
            AppointmentStatus.CANCELED_BY_CLIENT,
            AppointmentStatus.CANCELED_BY_ADMIN,
        }:
            notification.status = NotificationStatus.SKIPPED
            skipped += 1
            continue

        if vk_client is None:
            notification.status = NotificationStatus.SKIPPED
            skipped += 1
            continue

        try:
            message = _render_notification_message(db, notification)
            vk_client.send_message(user_id=client.vk_user_id, message=message)
            notification.message = message
            notification.status = NotificationStatus.SENT
            sent += 1
        except Exception as exc:  # noqa: BLE001
            notification.status = NotificationStatus.FAILED
            notification.message = f"{notification.message or ''}\nОшибка доставки: {exc}".strip()
            failed += 1

    db.commit()
    return {
        "processed": len(notifications),
        "sent": sent,
        "skipped": skipped,
        "failed": failed,
    }


def deliver_due_notifications(db: Session) -> dict[str, int]:
    settings = get_settings()
    if not settings.vk_access_token:
        return {"processed": 0, "sent": 0, "skipped": 0, "failed": 0}
    try:
        return process_due_notifications(db)
    except Exception:  # noqa: BLE001
        db.rollback()
        return {"processed": 0, "sent": 0, "skipped": 0, "failed": 1}
