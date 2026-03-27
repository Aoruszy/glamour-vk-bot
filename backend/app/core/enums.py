from enum import Enum


class ClientStatus(str, Enum):
    NEW = "new"
    ACTIVE = "active"
    VIP = "vip"
    BLOCKED = "blocked"


class AppointmentStatus(str, Enum):
    NEW = "new"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELED_BY_CLIENT = "canceled_by_client"
    CANCELED_BY_ADMIN = "canceled_by_admin"
    RESCHEDULED = "rescheduled"
    NO_SHOW = "no_show"


class NotificationType(str, Enum):
    BOOKING_CONFIRMATION = "booking_confirmation"
    REMINDER_24H = "reminder_24h"
    REMINDER_2H = "reminder_2h"
    CANCELLATION = "cancellation"
    RESCHEDULE = "reschedule"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    SKIPPED = "skipped"
    FAILED = "failed"


class ActorRole(str, Enum):
    SYSTEM = "system"
    CLIENT = "client"
    ADMIN = "admin"
    MASTER = "master"
