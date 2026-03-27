import logging
import threading

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import get_settings
from app.schemas.vk import VkBotResponse, VkEvent
from app.services.vk import build_keyboard, handle_vk_event
from app.services.vk_api import VkApiClient

router = APIRouter(prefix="/vk", tags=["vk"])
logger = logging.getLogger(__name__)


def _send_vk_reply(*, access_token: str, api_version: str, user_id: int, message: str, buttons: list[str]) -> None:
    try:
        client = VkApiClient(
            access_token=access_token,
            api_version=api_version,
        )
        client.send_message(
            user_id=user_id,
            message=message,
            keyboard=build_keyboard(buttons),
        )
    except Exception:
        logger.exception("VK send_message failed for user_id=%s", user_id)


def _dispatch_vk_reply(*, access_token: str, api_version: str, user_id: int, message: str, buttons: list[str]) -> None:
    threading.Thread(
        target=_send_vk_reply,
        kwargs={
            "access_token": access_token,
            "api_version": api_version,
            "user_id": user_id,
            "message": message,
            "buttons": buttons,
        },
        daemon=True,
    ).start()


@router.post("/events", response_model=None)
def receive_vk_event(
    event: VkEvent,
    db: Session = Depends(get_db),
) -> VkBotResponse | PlainTextResponse:
    settings = get_settings()
    if event.secret is not None and event.secret != settings.vk_callback_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Неверный секретный ключ Callback API.")
    if event.type != "confirmation" and event.type != "message_new":
        return PlainTextResponse("ok")
    result = handle_vk_event(db, event, settings.vk_confirmation_token)
    if isinstance(result, str):
        return PlainTextResponse(result)
    if not result.reply_text.strip():
        return PlainTextResponse("ok")

    from_id = event.object.message.from_id if event.object and event.object.message else None
    if from_id is not None and settings.vk_access_token:
        _dispatch_vk_reply(
            access_token=settings.vk_access_token,
            api_version=settings.vk_api_version,
            user_id=from_id,
            message=result.reply_text,
            buttons=result.buttons,
        )
        return PlainTextResponse("ok")

    return result
