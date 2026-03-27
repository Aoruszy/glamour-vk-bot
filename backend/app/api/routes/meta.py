from fastapi import APIRouter

router = APIRouter(tags=["meta"])


@router.get("/meta")
async def get_meta() -> dict[str, object]:
    return {
        "product_name": "Glamour",
        "project_type": "Beauty salon CRM with VK bot",
        "mvp_modules": [
            "clients",
            "services",
            "masters",
            "schedules",
            "appointments",
            "notifications",
            "stats",
            "vk",
        ],
    }
