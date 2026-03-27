from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import get_settings
from app.schemas.vk import VkBotResponse, VkEvent
from app.services.vk import build_keyboard, handle_vk_event
from app.services.vk_api import VkApiClient

router = APIRouter(prefix="/vk", tags=["vk"])


@router.post("/events", response_model=VkBotResponse | str)
def receive_vk_event(event: VkEvent, db: Session = Depends(get_db)) -> VkBotResponse | str:
    settings = get_settings()
    if event.secret is not None and event.secret != settings.vk_callback_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid VK callback secret.")
    result = handle_vk_event(db, event, settings.vk_confirmation_token)
    if isinstance(result, str):
        return result

    from_id = event.object.message.from_id if event.object and event.object.message else None
    if from_id is not None and settings.vk_access_token:
        client = VkApiClient(
            access_token=settings.vk_access_token,
            api_version=settings.vk_api_version,
        )
        client.send_message(
            user_id=from_id,
            message=result.reply_text,
            keyboard=build_keyboard(result.buttons),
        )
        return "ok"

    return result
