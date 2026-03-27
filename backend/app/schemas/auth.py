from app.schemas.common import ORMModel


class LoginRequest(ORMModel):
    username: str
    password: str


class TokenResponse(ORMModel):
    access_token: str
    token_type: str = "bearer"
    username: str


class AdminIdentity(ORMModel):
    username: str
    role: str = "admin"
