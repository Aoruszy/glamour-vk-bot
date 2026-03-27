from __future__ import annotations

import logging
import socket
from contextlib import contextmanager
from secrets import randbelow
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


@contextmanager
def _force_ipv4_dns() -> None:
    original_getaddrinfo = socket.getaddrinfo

    def ipv4_getaddrinfo(
        host: str,
        port: int,
        family: int = 0,
        type: int = 0,
        proto: int = 0,
        flags: int = 0,
    ):
        return original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)

    socket.getaddrinfo = ipv4_getaddrinfo
    try:
        yield
    finally:
        socket.getaddrinfo = original_getaddrinfo


class VkApiClient:
    def __init__(self, *, access_token: str, api_version: str) -> None:
        self.access_token = access_token
        self.api_version = api_version

    def send_message(
        self,
        *,
        user_id: int,
        message: str,
        keyboard: str | None = None,
    ) -> dict[str, object]:
        payload: dict[str, object] = {
            "user_id": user_id,
            "message": message,
            "random_id": randbelow(2_147_483_647),
            "access_token": self.access_token,
            "v": self.api_version,
        }
        if keyboard:
            payload["keyboard"] = keyboard

        body = urlencode(payload).encode("utf-8")
        request = Request(
            "https://api.vk.com/method/messages.send",
            data=body,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        with _force_ipv4_dns():
            with urlopen(request, timeout=5) as response:
                raw = response.read().decode("utf-8")

        import json

        parsed = json.loads(raw)
        if "error" in parsed:
            error_message = parsed["error"].get("error_msg", "VK API request failed.")
            logger.warning("VK API returned error for user_id=%s: %s", user_id, error_message)
            raise RuntimeError(error_message)
        return parsed
