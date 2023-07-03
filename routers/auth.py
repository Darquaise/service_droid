import aiohttp
from fastapi import Depends, Cookie
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta

from classes import Settings, Credentials

from .typing_classes import TokenResponse, TokenGrantPayload, User, GuildPreview
from .token_db import TokenDB
from .exceptions import Unauthorized, RateLimited, InvalidCode

# Discord URLs
DISCORD_URL = "https://discord.com"
DISCORD_API_URL = f"{DISCORD_URL}/api/v8"
DISCORD_OAUTH_URL = f"{DISCORD_URL}/api/oauth2"
DISCORD_TOKEN_URL = f"{DISCORD_OAUTH_URL}/token"
DISCORD_OAUTH_AUTHENTICATION_URL = f"{DISCORD_OAUTH_URL}/authorize"

# OAuth stuff
ALGORITHM: str = 'HS256'
ACCESS_TOKEN_EXPIRES_DAYS: int = 7
SCOPES = "%20".join(("identify", "guilds"))

OAUTH_2_SCHEME = OAuth2PasswordBearer(tokenUrl='token')
pwd_context = CryptContext(schemes=['bcrypt'])


class AuthContainer:
    cred: Credentials
    client: aiohttp.ClientSession | None = None
    tokens: TokenDB

    @classmethod
    async def start_session(cls, settings: Settings):
        cls.cred = settings.credentials
        cls.tokens = TokenDB()
        cls.client = aiohttp.ClientSession()


# Requests to discord
async def request(route: str, token: str = None, method: str = "GET"):
    headers: dict = {}
    if token:
        headers = {"Authorization": f"Bearer {token}"}
    if method == "GET":
        async with AuthContainer.client.get(f"{DISCORD_API_URL}{route}", headers=headers) as resp:
            data = await resp.json()
    elif method == "POST":
        async with AuthContainer.client.post(f"{DISCORD_API_URL}{route}", headers=headers) as resp:
            data = await resp.json()
    else:
        raise Exception("Other HTTP than GET and POST are currently not Supported")
    if resp.status == 401:
        raise Unauthorized
    if resp.status == 429:
        raise RateLimited(data, resp.headers)
    return data


# ### login
async def login_url():
    client_id = f"client_id={AuthContainer.cred.client_id}"
    redirect_uri = f"redirect_uri={AuthContainer.cred.redirect_uri}"
    return f"{DISCORD_OAUTH_AUTHENTICATION_URL}?{client_id}&{redirect_uri}&scope={SCOPES}&response_type=code"


async def redeem_code(code: str) -> TokenResponse:
    payload: TokenGrantPayload = {
        "client_id": str(AuthContainer.cred.client_id),
        "client_secret": AuthContainer.cred.client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": AuthContainer.cred.redirect_uri,
    }
    async with AuthContainer.client.post(DISCORD_TOKEN_URL, data=payload) as resp:
        data = await resp.json()
        print(data)
        if 'error' in data:
            raise InvalidCode
        return data


async def get_user_from_token(token: str) -> User:
    return User(**(await request('/users/@me', token)))


async def get_user_guilds_from_token(token: str) -> list[GuildPreview]:
    return await request('/users/@me/guilds', token)


async def generate_token(token_data: TokenResponse = Depends(redeem_code)):
    user = await get_user_from_token(token_data['access_token'])
    expires_at = int((datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRES_DAYS)).timestamp())

    AuthContainer.tokens.set_entry(user.id, token_data, expires_at)

    to_encode = {
        'user_id': int(user.id),
        'expires_at': expires_at
    }

    encoded_jwt = jwt.encode(to_encode, AuthContainer.cred.client_secret, algorithm=ALGORITHM)
    return encoded_jwt


# ### authentication
async def get_user_id_from_access_token(access_token: str = Cookie()) -> int:
    try:
        payload = jwt.decode(access_token, AuthContainer.cred.client_secret, algorithms=[ALGORITHM])
        user_id = payload.get('user_id')
        if user_id is None:
            raise Unauthorized

    except JWTError:
        raise Unauthorized

    return user_id


async def get_token_from_user_id(user_id: int = Depends(get_user_id_from_access_token)) -> str:
    access_token_data = AuthContainer.tokens.get_entry(user_id)
    if not access_token_data:
        raise Unauthorized

    return access_token_data['access_token']


async def user_is_authenticated(token: str = Depends(get_token_from_user_id)):
    try:
        await request('/oauth2/@me', token)
        return True
    except Unauthorized:
        return False
