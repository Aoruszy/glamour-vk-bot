from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.enums import ActorRole, AppointmentStatus
from app.models.appointment import Appointment
from app.models.bot_session import BotSession
from app.models.client import Client
from app.models.master import Master
from app.models.service import Service, ServiceCategory
from app.schemas.appointment import AppointmentCreate
from app.schemas.vk import VkBotResponse, VkEvent
from app.services.appointments import create_appointment, get_available_slots

SPAM_WINDOW_SECONDS = 8
SPAM_MAX_MESSAGES = 10
DUPLICATE_WINDOW_SECONDS = 6
DUPLICATE_MAX_MESSAGES = 3
SPAM_MUTE_SECONDS = 20

MAIN_BUTTONS = [
    "Записаться",
    "Мои записи",
    "Отменить запись",
    "Услуги",
    "Мастера",
    "Контакты",
    "Помощь",
]

GLOBAL_COMMANDS = {"в меню", "главное меню", "отмена", "меню"}
BACK_COMMANDS = {"назад"}
ANY_MASTER_LABEL = "Любой свободный мастер"
CANCEL_PREFIX = "Отменить №"


def _appointment_status_label(status: AppointmentStatus) -> str:
    labels = {
        AppointmentStatus.NEW: "Новая",
        AppointmentStatus.CONFIRMED: "Подтверждена",
        AppointmentStatus.COMPLETED: "Завершена",
        AppointmentStatus.CANCELED_BY_CLIENT: "Отменена вами",
        AppointmentStatus.CANCELED_BY_ADMIN: "Отменена салоном",
        AppointmentStatus.RESCHEDULED: "Перенесена",
        AppointmentStatus.NO_SHOW: "Неявка",
    }
    return labels.get(status, status.value)


def _appointment_short_label(appointment: Appointment) -> str:
    return (
        f"№{appointment.id} {appointment.appointment_date} "
        f"{appointment.start_time.strftime('%H:%M')}"
    )


def _appointment_details_label(db: Session, appointment: Appointment) -> str:
    service = db.get(Service, appointment.service_id)
    master = db.get(Master, appointment.master_id)
    service_name = service.name if service else "Услуга не указана"
    master_name = master.full_name if master else "Мастер не назначен"
    return "\n".join(
        [
            f"№{appointment.id} • {service_name}",
            f"Мастер: {master_name}",
            f"Дата: {appointment.appointment_date.strftime('%d.%m.%Y')} в {appointment.start_time.strftime('%H:%M')}",
            f"Статус: {_appointment_status_label(appointment.status)}",
        ]
    )


def _button_color(label: str) -> str:
    if label == "Записаться":
        return "primary"
    if label in {"В меню", "Главное меню"}:
        return "primary"
    if label.startswith("Отменить"):
        return "negative"
    return "secondary"


def _button_payload(label: str) -> dict[str, object]:
    return {
        "action": {
            "type": "text",
            "label": label,
        },
        "color": _button_color(label),
    }


def _chunk_buttons(buttons: list[str], size: int) -> list[list[str]]:
    return [buttons[index : index + size] for index in range(0, len(buttons), size)]


def _is_navigation_button(label: str) -> bool:
    return label in {"Назад", "В меню", "Главное меню"}


def _keyboard_rows(buttons: list[str]) -> list[list[dict[str, object]]]:
    if buttons == MAIN_BUTTONS:
        return [
            [_button_payload("Записаться"), _button_payload("Мои записи")],
            [_button_payload("Отменить запись"), _button_payload("Услуги")],
            [_button_payload("Мастера"), _button_payload("Контакты")],
            [_button_payload("Помощь")],
        ]

    navigation = [button for button in buttons if _is_navigation_button(button)]
    content = [button for button in buttons if not _is_navigation_button(button)]

    rows: list[list[dict[str, object]]] = []
    for group in _chunk_buttons(content, 2):
        rows.append([_button_payload(button) for button in group])

    if navigation:
        rows.append([_button_payload(button) for button in navigation])

    return rows or [[_button_payload("В меню")]]


def build_keyboard(buttons: list[str]) -> str:
    keyboard = {
        "one_time": False,
        "inline": False,
        "buttons": _keyboard_rows(buttons),
    }
    return json.dumps(keyboard, ensure_ascii=False)


def _response(text: str, buttons: list[str] | None = None) -> VkBotResponse:
    return VkBotResponse(reply_text=text, buttons=buttons or MAIN_BUTTONS)


def _session_payload(session: BotSession) -> dict[str, object]:
    try:
        return json.loads(session.payload)
    except json.JSONDecodeError:
        return {}


def _save_session(session: BotSession, *, state: str, payload: dict[str, object]) -> None:
    current_payload = _session_payload(session)
    spam_meta = current_payload.get("_spam")
    merged_payload = dict(payload)
    if spam_meta is not None and "_spam" not in merged_payload:
        merged_payload["_spam"] = spam_meta
    session.state = state
    session.payload = json.dumps(merged_payload, ensure_ascii=False)


def _reset_session(session: BotSession) -> None:
    _save_session(session, state="idle", payload={})


def _spam_now() -> datetime:
    return datetime.utcnow()


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _store_spam_meta(session: BotSession, payload: dict[str, object], spam_meta: dict[str, object]) -> None:
    updated_payload = dict(payload)
    updated_payload["_spam"] = spam_meta
    _save_session(session, state=session.state, payload=updated_payload)


def _check_spam(session: BotSession, text: str) -> VkBotResponse | None:
    payload = _session_payload(session)
    spam_meta = dict(payload.get("_spam", {}))
    now = _spam_now()
    normalized = text.strip().lower()

    mute_until = _parse_dt(spam_meta.get("mute_until"))
    if mute_until is not None and now < mute_until:
        _store_spam_meta(
            session,
            payload,
            {
                **spam_meta,
                "last_message_at": now.isoformat(),
                "last_text": normalized,
            },
        )
        return VkBotResponse(reply_text="", buttons=[])

    window_started_at = _parse_dt(spam_meta.get("window_started_at"))
    if window_started_at is None or (now - window_started_at).total_seconds() > SPAM_WINDOW_SECONDS:
        window_started_at = now
        message_count = 0
    else:
        message_count = int(spam_meta.get("message_count", 0))

    last_message_at = _parse_dt(spam_meta.get("last_message_at"))
    duplicate_count = int(spam_meta.get("duplicate_count", 0))
    if (
        normalized
        and normalized == spam_meta.get("last_text")
        and last_message_at is not None
        and (now - last_message_at).total_seconds() <= DUPLICATE_WINDOW_SECONDS
    ):
        duplicate_count += 1
    else:
        duplicate_count = 1

    message_count += 1
    next_meta = {
        "window_started_at": window_started_at.isoformat(),
        "message_count": message_count,
        "last_message_at": now.isoformat(),
        "last_text": normalized,
        "duplicate_count": duplicate_count,
    }

    if message_count > SPAM_MAX_MESSAGES or duplicate_count > DUPLICATE_MAX_MESSAGES:
        next_meta["mute_until"] = (now + timedelta(seconds=SPAM_MUTE_SECONDS)).isoformat()
        _store_spam_meta(session, payload, next_meta)
        return _response(
            "??????? ????? ????????? ??????. ????????? ???????, ? ? ???????? ???????? ? ???????.",
            ["? ????"],
        )

    _store_spam_meta(session, payload, next_meta)
    return None


def _get_or_create_session(db: Session, vk_user_id: int) -> BotSession:
    session = db.scalar(select(BotSession).where(BotSession.vk_user_id == vk_user_id))
    if session:
        return session

    session = BotSession(vk_user_id=vk_user_id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _ensure_client(db: Session, vk_user_id: int) -> Client:
    client = db.scalar(select(Client).where(Client.vk_user_id == vk_user_id))
    if client:
        return client

    client = Client(vk_user_id=vk_user_id)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


def _main_menu_text() -> str:
    settings = get_settings()
    return (
        f"Здравствуйте! Я бот {settings.salon_name}. "
        "Помогу записаться, посмотреть ваши записи и получить информацию о салоне."
    )


def _require_profile_step(client: Client, session: BotSession) -> VkBotResponse | None:
    payload = _session_payload(session)
    if not client.full_name:
        payload["after_profile"] = "booking"
        _save_session(session, state="awaiting_name", payload=payload)
        return _response(
            "Для записи сначала подскажите, пожалуйста, ваше имя.",
            ["В меню"],
        )
    if not client.phone:
        payload["after_profile"] = "booking"
        _save_session(session, state="awaiting_phone", payload=payload)
        return _response(
            "Спасибо! Теперь отправьте номер телефона в формате +79990001122.",
            ["Назад", "В меню"],
        )
    return None


def _active_appointments(db: Session, client_id: int) -> list[Appointment]:
    return list(
        db.scalars(
            select(Appointment)
            .where(
                Appointment.client_id == client_id,
                Appointment.status.in_(
                    [
                        AppointmentStatus.NEW,
                        AppointmentStatus.CONFIRMED,
                        AppointmentStatus.RESCHEDULED,
                    ]
                ),
            )
            .order_by(Appointment.appointment_date, Appointment.start_time)
        )
    )


def _format_services(db: Session) -> str:
    services = db.scalars(select(Service).where(Service.is_active.is_(True)).order_by(Service.name)).all()
    if not services:
        return "Услуги пока не добавлены."
    return "Доступные услуги:\n" + "\n".join(
        f"- {service.name}: {service.price} RUB, {service.duration_minutes} мин"
        for service in services
    )


def _format_masters(db: Session) -> str:
    masters = db.scalars(select(Master).where(Master.is_active.is_(True)).order_by(Master.full_name)).all()
    if not masters:
        return "Мастера пока не добавлены."
    return "Наши мастера:\n" + "\n".join(
        f"- {master.full_name}" + (f", {master.specialization}" if master.specialization else "")
        for master in masters
    )


def _format_appointments(db: Session, client_id: int) -> str:
    appointments = _active_appointments(db, client_id)
    if not appointments:
        return "У вас нет активных записей."
    return "Ваши активные записи:\n\n" + "\n\n".join(
        _appointment_details_label(db, appointment)
        for appointment in appointments[:6]
    )


def _format_cancelable_appointments(appointments: list[Appointment]) -> str:
    if not appointments:
        return "У вас нет активных записей для отмены."
    return "Активные записи для отмены:\n" + "\n".join(
        f"- {_appointment_short_label(appointment)}"
        for appointment in appointments[:6]
    )


def _contacts_text() -> str:
    settings = get_settings()
    lines = [
        f"{settings.salon_name}",
        f"Адрес: {settings.salon_address}",
        f"Телефон: {settings.salon_phone}",
        f"Режим работы: {settings.salon_working_hours}",
    ]
    if settings.salon_map_url:
        lines.append(f"Карта: {settings.salon_map_url}")
    if settings.salon_website_url:
        lines.append(f"Сайт: {settings.salon_website_url}")
    return "\n".join(lines)


def _help_text() -> str:
    return (
        "Я могу помочь записаться на услугу, показать ваши записи и дать контакты салона.\n"
        "Основные команды: Записаться, Мои записи, Услуги, Мастера, Контакты."
    )


def _start_booking(db: Session, client: Client, session: BotSession) -> VkBotResponse:
    profile_step = _require_profile_step(client, session)
    if profile_step is not None:
        db.commit()
        return profile_step
    return _show_categories(db, session)


def _show_categories(db: Session, session: BotSession) -> VkBotResponse:
    categories = list(
        db.scalars(
            select(ServiceCategory)
            .where(ServiceCategory.is_active.is_(True))
            .order_by(ServiceCategory.name)
        )
    )
    if not categories:
        return _response("Категории услуг пока не настроены.")

    payload = _session_payload(session)
    payload["categories"] = {category.name: category.id for category in categories[:8]}
    _save_session(session, state="choosing_category", payload=payload)
    db.commit()
    return _response(
        "Выберите категорию услуги.",
        [category.name for category in categories[:8]] + ["В меню"],
    )


def _show_services(db: Session, session: BotSession, category_id: int) -> VkBotResponse:
    services = list(
        db.scalars(
            select(Service)
            .where(Service.category_id == category_id, Service.is_active.is_(True))
            .order_by(Service.name)
        )
    )
    if not services:
        return _response("В этой категории пока нет активных услуг.", ["Назад", "В меню"])

    payload = _session_payload(session)
    payload["category_id"] = category_id
    payload["services"] = {service.name: service.id for service in services[:8]}
    _save_session(session, state="choosing_service", payload=payload)
    db.commit()
    return _response(
        "Теперь выберите услугу.",
        [service.name for service in services[:8]] + ["Назад", "В меню"],
    )


def _show_masters(db: Session, session: BotSession, service_id: int) -> VkBotResponse:
    masters = list(
        db.scalars(
            select(Master)
            .join(Master.services)
            .where(Service.id == service_id, Master.is_active.is_(True))
            .order_by(Master.full_name)
        ).unique()
    )
    if not masters:
        return _response("Для этой услуги пока нет активных мастеров.", ["Назад", "В меню"])

    payload = _session_payload(session)
    payload["service_id"] = service_id
    payload["masters"] = {master.full_name: master.id for master in masters[:8]}
    _save_session(session, state="choosing_master", payload=payload)
    db.commit()
    return _response(
        "Выберите мастера или доверьтесь свободному специалисту.",
        [ANY_MASTER_LABEL] + [master.full_name for master in masters[:7]] + ["Назад", "В меню"],
    )


def _show_dates(db: Session, session: BotSession, service_id: int, master_id: int | None) -> VkBotResponse:
    available_dates: dict[str, str] = {}
    today = date.today()
    for offset in range(14):
        current_date = today + timedelta(days=offset)
        slots = get_available_slots(
            db,
            service_id=service_id,
            work_date=current_date,
            master_id=master_id,
        )
        if slots:
            available_dates[current_date.isoformat()] = current_date.isoformat()
        if len(available_dates) >= 6:
            break

    if not available_dates:
        return _response("На ближайшие дни свободных окон нет. Попробуйте позже.", ["Назад", "В меню"])

    payload = _session_payload(session)
    payload["master_id"] = master_id
    payload["dates"] = available_dates
    _save_session(session, state="choosing_date", payload=payload)
    db.commit()
    return _response(
        "Выберите дату визита.",
        list(available_dates.keys()) + ["Назад", "В меню"],
    )


def _show_slots(db: Session, session: BotSession, work_date: date) -> VkBotResponse:
    payload = _session_payload(session)
    service_id = int(payload["service_id"])
    master_id = payload.get("master_id")
    slots = get_available_slots(
        db,
        service_id=service_id,
        work_date=work_date,
        master_id=int(master_id) if master_id is not None else None,
    )
    if not slots:
        return _response("На выбранную дату свободных окон нет.", ["Назад", "В меню"])

    slot_map = {
        slot.start_time.strftime("%H:%M"): {
            "start_time": slot.start_time.strftime("%H:%M:%S"),
            "master_ids": slot.master_ids,
        }
        for slot in slots[:8]
    }
    payload["appointment_date"] = work_date.isoformat()
    payload["slots"] = slot_map
    _save_session(session, state="choosing_slot", payload=payload)
    db.commit()
    return _response(
        "Выберите удобное время.",
        list(slot_map.keys()) + ["Назад", "В меню"],
    )


def _complete_booking(db: Session, client: Client, session: BotSession, slot_label: str) -> VkBotResponse:
    payload = _session_payload(session)
    slot_data = payload.get("slots", {}).get(slot_label)
    if not slot_data:
        return _response("Не удалось распознать выбранное время. Попробуйте еще раз.", ["Назад", "В меню"])

    appointment = create_appointment(
        db,
        AppointmentCreate(
            client_id=client.id,
            service_id=int(payload["service_id"]),
            master_id=int(payload["master_id"]) if payload.get("master_id") is not None else None,
            appointment_date=date.fromisoformat(str(payload["appointment_date"])),
            start_time=datetime.strptime(str(slot_data["start_time"]), "%H:%M:%S").time(),
            created_by=ActorRole.CLIENT,
        ),
    )
    service = db.get(Service, appointment.service_id)
    master = db.get(Master, appointment.master_id)
    _reset_session(session)
    db.commit()
    return _response(
        "Запись подтверждена!\n"
        f"Услуга: {service.name}\n"
        f"Мастер: {master.full_name}\n"
        f"Дата: {appointment.appointment_date}\n"
        f"Время: {appointment.start_time.strftime('%H:%M')}",
    )


def _start_cancel_flow(db: Session, client: Client, session: BotSession) -> VkBotResponse:
    appointments = _active_appointments(db, client.id)
    if not appointments:
        return _response("У вас нет активных записей для отмены.")

    payload = _session_payload(session)
    payload["cancel_options"] = {
        f"Отменить {_appointment_short_label(appointment)}": appointment.id for appointment in appointments[:6]
    }
    _save_session(session, state="choosing_cancel", payload=payload)
    db.commit()
    return _response(
        _format_cancelable_appointments(appointments[:6]),
        list(payload["cancel_options"].keys()) + ["Назад", "В меню"],
    )


def _cancel_selected_appointment(db: Session, client: Client, session: BotSession, label: str) -> VkBotResponse:
    payload = _session_payload(session)
    appointment_id = payload.get("cancel_options", {}).get(label)
    if not appointment_id:
        return _response("Не удалось распознать выбранную запись.", ["В меню"])

    appointment = db.get(Appointment, int(appointment_id))
    if not appointment or appointment.client_id != client.id:
        return _response("Запись не найдена.", ["В меню"])

    from app.services.appointments import cancel_appointment

    cancel_appointment(
        db,
        appointment=appointment,
        actor_role=ActorRole.CLIENT,
        reason="Canceled from VK bot",
    )
    _reset_session(session)
    db.commit()
    return _response(f"Запись {_appointment_short_label(appointment)} отменена.")


def _cancel_appointment_by_label(db: Session, client: Client, session: BotSession, label: str) -> VkBotResponse:
    match = re.search(r"(?:#|№)(\d+)", label)
    if not match:
        return _start_cancel_flow(db, client, session)

    appointment = db.get(Appointment, int(match.group(1)))
    if not appointment or appointment.client_id != client.id:
        return _response("Запись не найдена.", ["В меню"])

    from app.services.appointments import cancel_appointment

    cancel_appointment(
        db,
        appointment=appointment,
        actor_role=ActorRole.CLIENT,
        reason="Canceled from VK bot",
    )
    _reset_session(session)
    db.commit()
    return _response(f"Запись {_appointment_short_label(appointment)} отменена.")


def _go_back(db: Session, client: Client, session: BotSession) -> VkBotResponse:
    payload = _session_payload(session)
    if session.state == "awaiting_phone":
        _save_session(session, state="awaiting_name", payload=payload)
        db.commit()
        return _response("Хорошо, давайте заново. Как вас зовут?", ["В меню"])
    if session.state == "choosing_cancel":
        _reset_session(session)
        db.commit()
        appointments = _active_appointments(db, client.id)
        buttons = ["Отменить запись", "В меню"] if appointments else MAIN_BUTTONS
        return _response(_format_appointments(db, client.id), buttons)
    if session.state == "choosing_service":
        return _show_categories(db, session)
    if session.state == "choosing_master":
        return _show_services(db, session, int(payload["category_id"]))
    if session.state == "choosing_date":
        return _show_masters(db, session, int(payload["service_id"]))
    if session.state == "choosing_slot":
        return _show_dates(
            db,
            session,
            int(payload["service_id"]),
            int(payload["master_id"]) if payload.get("master_id") is not None else None,
        )
    _reset_session(session)
    db.commit()
    return _response(_main_menu_text())


def _handle_stateful_message(db: Session, client: Client, session: BotSession, text: str) -> VkBotResponse:
    payload = _session_payload(session)

    if session.state == "awaiting_name":
        client.full_name = text.strip().title()
        db.add(client)
        if client.phone:
            _reset_session(session)
            db.commit()
            return _start_booking(db, client, session)
        payload["after_profile"] = payload.get("after_profile", "booking")
        _save_session(session, state="awaiting_phone", payload=payload)
        db.commit()
        return _response(
            "Спасибо! Теперь отправьте номер телефона в формате +79990001122.",
            ["Назад", "В меню"],
        )

    if session.state == "awaiting_phone":
        phone = text.strip()
        if not re.fullmatch(r"\+?\d[\d\-() ]{9,18}", phone):
            return _response("Номер не похож на телефон. Попробуйте формат +79990001122.", ["Назад", "В меню"])
        client.phone = phone
        db.add(client)
        _reset_session(session)
        db.commit()
        if payload.get("after_profile") == "booking":
            return _start_booking(db, client, session)
        return _response("Контакт сохранен. Чем могу помочь дальше?")

    if session.state == "choosing_category":
        category_id = payload.get("categories", {}).get(text)
        if not category_id:
            return _response("Выберите категорию кнопкой ниже.", list(payload.get("categories", {}).keys()) + ["В меню"])
        return _show_services(db, session, int(category_id))

    if session.state == "choosing_service":
        service_id = payload.get("services", {}).get(text)
        if not service_id:
            return _response("Выберите услугу кнопкой ниже.", list(payload.get("services", {}).keys()) + ["Назад", "В меню"])
        return _show_masters(db, session, int(service_id))

    if session.state == "choosing_master":
        if text == ANY_MASTER_LABEL:
            return _show_dates(db, session, int(payload["service_id"]), None)
        master_id = payload.get("masters", {}).get(text)
        if not master_id:
            return _response("Выберите мастера кнопкой ниже.", [ANY_MASTER_LABEL] + list(payload.get("masters", {}).keys()) + ["Назад", "В меню"])
        return _show_dates(db, session, int(payload["service_id"]), int(master_id))

    if session.state == "choosing_date":
        selected_date = payload.get("dates", {}).get(text)
        if not selected_date:
            return _response("Выберите дату кнопкой ниже.", list(payload.get("dates", {}).keys()) + ["Назад", "В меню"])
        return _show_slots(db, session, date.fromisoformat(str(selected_date)))

    if session.state == "choosing_slot":
        return _complete_booking(db, client, session, text)

    if session.state == "choosing_cancel":
        return _cancel_selected_appointment(db, client, session, text)

    return _response(_help_text())


def handle_vk_event(db: Session, event: VkEvent, confirm_token: str) -> str | VkBotResponse:
    if event.type == "confirmation":
        return confirm_token
    if event.type != "message_new":
        return _response("Событие принято.")

    text = (event.object.message.text if event.object and event.object.message else "").strip()
    normalized = text.lower()
    from_id = event.object.message.from_id if event.object and event.object.message else None
    if from_id is None:
        return _response("Не удалось определить пользователя VK.")

    client = _ensure_client(db, from_id)
    session = _get_or_create_session(db, from_id)

    spam_response = _check_spam(session, text)
    if spam_response is not None:
        db.commit()
        return spam_response

    if normalized in GLOBAL_COMMANDS:
        _reset_session(session)
        db.commit()
        return _response(_main_menu_text())

    if normalized in BACK_COMMANDS:
        return _go_back(db, client, session)

    if session.state != "idle":
        return _handle_stateful_message(db, client, session, text)

    if normalized in {"начать", "start", "привет"}:
        _reset_session(session)
        db.commit()
        return _response(_main_menu_text())
    if normalized == "записаться":
        return _start_booking(db, client, session)
    if normalized == "услуги":
        return _response(_format_services(db))
    if normalized == "мастера":
        return _response(_format_masters(db))
    if normalized == "мои записи":
        appointments = _active_appointments(db, client.id)
        buttons = ["Отменить запись", "В меню"] if appointments else MAIN_BUTTONS
        return _response(_format_appointments(db, client.id), buttons)
    if normalized == "отменить запись":
        return _start_cancel_flow(db, client, session)
    if normalized.startswith(CANCEL_PREFIX.lower()):
        return _cancel_appointment_by_label(db, client, session, text)
    if normalized in {"контакты", "адрес"}:
        return _response(_contacts_text())
    if normalized == "помощь":
        return _response(_help_text())

    return _response(
        "Доступные команды: Записаться, Мои записи, Услуги, Мастера, Контакты, Помощь."
    )
