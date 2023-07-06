from discord import Permissions
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from datetime import datetime

from .auth import login_url, generate_token, get_token_from_user_id, get_user_from_token, get_user_guilds_from_token, \
    user_is_authenticated
from .typing_classes import User, GuildPreview

router = APIRouter(prefix='/auth')


@router.get("/login_link")
async def login_link():
    return JSONResponse({
        'url': await login_url()
    })


@router.get("/callback")
async def callback(token: str = Depends(generate_token)):
    response = JSONResponse({
        'successful': True
    })
    response.set_cookie(key='access_token', value=str(token))
    return response


@router.get("/user", response_model=User)
async def get_user(token: str = Depends(get_token_from_user_id)):
    user = await get_user_from_token(token)
    return user


@router.get("/authenticated")
async def is_authenticated(is_auth: bool = Depends(user_is_authenticated)):
    return JSONResponse({
        'successful': is_auth
    })


@router.get("/user/guilds")
async def get_guilds(request: Request, token: str = Depends(get_token_from_user_id)):
    start = datetime.utcnow()

    user_guilds: list[GuildPreview] = await get_user_guilds_from_token(token)

    nexxt = datetime.utcnow()
    print(f"get from discord: {(start - nexxt).microseconds}ms")
    start = nexxt

    available_guilds: list[GuildPreview] = []
    optional_guilds: list[GuildPreview] = []
    bot_guilds: list[int] = [g.id for g in request.app.bot.guilds]

    for guild in user_guilds:
        perm = Permissions(int(guild['permissions']))
        if perm.administrator or perm.manage_guild:
            if int(guild['id']) in bot_guilds:
                available_guilds.append(guild)
            else:
                optional_guilds.append(guild)

    nexxt = datetime.utcnow()
    print(f"merge guilds: {(start - nexxt).microseconds}ms")

    return JSONResponse({
        'available_guilds': available_guilds,
        'optional_guilds': optional_guilds
    })
