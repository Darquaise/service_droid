from pydantic import BaseModel
from typing import TypedDict, Literal


class Role(BaseModel):
    id: int
    name: str
    color: int
    position: int
    permissions: int
    managed: bool
    mentionable: bool


class User(BaseModel):
    id: str
    username: str
    discriminator: str
    avatar: str | None
    avatar_url: str | None
    locale: str
    email: str | None
    bot: bool | None
    mfa_enabled: bool
    flags: int
    premium_type: int | None
    public_flags: int

    def __init__(self, **data):
        super().__init__(**data)
        if self.avatar:
            self.avatar_url = f"https://cdn.discordapp.com/avatars/{self.id}/{self.avatar}.png"
        else:
            self.avatar_url = "https://cdn.discordapp.com/embed/avatars/1.png"


class GuildPreview(TypedDict):
    id: str
    name: str
    icon: str | None
    owner: bool
    permissions: int
    features: list[str]


class RefreshTokenPayload(TypedDict):
    client_id: str
    client_secret: str
    grant_type: Literal['refresh_token']
    refresh_token: str


class TokenGrantPayload(TypedDict):
    client_id: str
    client_secret: str
    grant_type: Literal['authorization_code']
    code: str
    redirect_uri: str


class TokenResponse(TypedDict):
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str
    scope: str


class TokenStorage(TypedDict):
    access_token: str
    token_expires_at: int
    refresh_token: str
    access_token_expires_at: int
