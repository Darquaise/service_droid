from discord import Permissions
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from datetime import datetime

from converters.links import transform_icon

from .auth import get_token_from_user_id, get_user_from_token, get_user_guilds_from_token
from .typing_classes import GuildPreview, User

router = APIRouter(prefix='/api/user')


@router.get("/")
async def get_user(token: str = Depends(get_token_from_user_id)):
    user: User = await get_user_from_token(token)
    return user


@router.get("/guilds")
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
            transform_icon(guild)
            if int(guild['id']) in bot_guilds:
                available_guilds.append(guild)
            else:
                optional_guilds.append(guild)

    nexxt = datetime.utcnow()
    print(f"merge guilds: {(start - nexxt).microseconds}ms")

    return JSONResponse({
        'availableGuilds': available_guilds,
        'optionalGuilds': optional_guilds
    })
