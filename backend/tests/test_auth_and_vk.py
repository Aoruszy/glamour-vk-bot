from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select

from app.api.routes.auth import login
from app.api.routes.vk import receive_vk_event
from app.config import get_settings
from app.core.security import verify_access_token
from app.models.appointment import Appointment
from app.schemas.auth import LoginRequest
from app.schemas.vk import VkBotResponse, VkEvent
from app.services.vk import handle_vk_event


def test_login_returns_valid_signed_token() -> None:
    settings = get_settings()
    response = login(LoginRequest(username=settings.admin_username, password=settings.admin_password))
    payload = verify_access_token(response.access_token, settings.auth_secret)

    assert payload is not None
    assert payload["sub"] == settings.admin_username


def test_login_rejects_invalid_credentials() -> None:
    try:
        login(LoginRequest(username="wrong", password="wrong"))
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("Expected HTTPException for invalid credentials")


def test_vk_confirmation_returns_confirmation_token(db_session) -> None:
    settings = get_settings()
    event = VkEvent(type="confirmation", secret=settings.vk_callback_secret)

    response = receive_vk_event(event, db_session)

    assert response == settings.vk_confirmation_token


def test_vk_message_returns_debug_payload_without_access_token(monkeypatch, db_session) -> None:
    monkeypatch.setenv("VK_ACCESS_TOKEN", "")
    get_settings.cache_clear()
    settings = get_settings()
    event = VkEvent.model_validate(
        {
            "type": "message_new",
            "secret": settings.vk_callback_secret,
            "object": {"message": {"from_id": 777, "text": "начать"}},
        }
    )

    response = receive_vk_event(event, db_session)

    assert isinstance(response, VkBotResponse)
    assert "Glamour" in response.reply_text


def test_vk_message_sends_via_vk_api_when_token_present(monkeypatch, db_session) -> None:
    sent_payload: dict[str, object] = {}

    class FakeVkApiClient:
        def __init__(self, *, access_token: str, api_version: str) -> None:
            sent_payload["access_token"] = access_token
            sent_payload["api_version"] = api_version

        def send_message(self, *, user_id: int, message: str, keyboard: str | None = None) -> dict[str, object]:
            sent_payload["user_id"] = user_id
            sent_payload["message"] = message
            sent_payload["keyboard"] = keyboard
            return {"response": 1}

    monkeypatch.setenv("VK_ACCESS_TOKEN", "vk-test-token")
    monkeypatch.setenv("VK_API_VERSION", "5.199")
    get_settings.cache_clear()
    monkeypatch.setattr("app.api.routes.vk.VkApiClient", FakeVkApiClient)

    settings = get_settings()
    event = VkEvent.model_validate(
        {
            "type": "message_new",
            "secret": settings.vk_callback_secret,
            "object": {"message": {"from_id": 778, "text": "услуги"}},
        }
    )

    response = receive_vk_event(event, db_session)

    assert response == "ok"
    assert sent_payload["access_token"] == "vk-test-token"
    assert sent_payload["user_id"] == 778
    assert "keyboard" in sent_payload


def test_vk_booking_flow_creates_appointment(db_session, seeded_booking_data) -> None:
    client = seeded_booking_data["client"]
    service = seeded_booking_data["service"]
    master = seeded_booking_data["master"]
    work_date = seeded_booking_data["work_date"]
    category_name = "Manicure"

    start_response = handle_vk_event(
        db_session,
        VkEvent.model_validate(
            {"type": "message_new", "object": {"message": {"from_id": client.vk_user_id, "text": "записаться"}}}
        ),
        "confirm-token",
    )
    assert isinstance(start_response, VkBotResponse)
    assert "категорию" in start_response.reply_text.lower()
    assert category_name in start_response.buttons

    service_response = handle_vk_event(
        db_session,
        VkEvent.model_validate(
            {"type": "message_new", "object": {"message": {"from_id": client.vk_user_id, "text": category_name}}}
        ),
        "confirm-token",
    )
    assert isinstance(service_response, VkBotResponse)
    assert service.name in service_response.buttons

    master_response = handle_vk_event(
        db_session,
        VkEvent.model_validate(
            {"type": "message_new", "object": {"message": {"from_id": client.vk_user_id, "text": service.name}}}
        ),
        "confirm-token",
    )
    assert isinstance(master_response, VkBotResponse)
    assert master.full_name in master_response.buttons

    date_response = handle_vk_event(
        db_session,
        VkEvent.model_validate(
            {"type": "message_new", "object": {"message": {"from_id": client.vk_user_id, "text": master.full_name}}}
        ),
        "confirm-token",
    )
    assert isinstance(date_response, VkBotResponse)
    assert work_date.isoformat() in date_response.buttons

    slot_response = handle_vk_event(
        db_session,
        VkEvent.model_validate(
            {"type": "message_new", "object": {"message": {"from_id": client.vk_user_id, "text": work_date.isoformat()}}}
        ),
        "confirm-token",
    )
    assert isinstance(slot_response, VkBotResponse)
    assert "10:00" in slot_response.buttons

    confirm_response = handle_vk_event(
        db_session,
        VkEvent.model_validate(
            {"type": "message_new", "object": {"message": {"from_id": client.vk_user_id, "text": "10:00"}}}
        ),
        "confirm-token",
    )
    assert isinstance(confirm_response, VkBotResponse)
    assert "Запись подтверждена" in confirm_response.reply_text

    appointments = list(db_session.scalars(select(Appointment).where(Appointment.client_id == client.id)))
    assert len(appointments) == 1


def test_vk_booking_flow_requests_profile_when_missing(db_session) -> None:
    response = handle_vk_event(
        db_session,
        VkEvent.model_validate(
            {"type": "message_new", "object": {"message": {"from_id": 555000, "text": "записаться"}}}
        ),
        "confirm-token",
    )

    assert isinstance(response, VkBotResponse)
    assert "ваше имя" in response.reply_text.lower()
