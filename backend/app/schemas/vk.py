from pydantic import BaseModel, Field


class VkMessageObject(BaseModel):
    text: str = ""
    from_id: int | None = None


class VkCallbackObject(BaseModel):
    message: VkMessageObject | None = None


class VkEvent(BaseModel):
    type: str
    group_id: int | None = None
    secret: str | None = None
    object: VkCallbackObject | None = Field(default=None, alias="object")


class VkBotResponse(BaseModel):
    ok: bool = True
    reply_text: str
    buttons: list[str] = []
