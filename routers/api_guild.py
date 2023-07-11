from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from classes import Guild

from .exceptions import Unauthorized
from .auth import get_user_id_from_access_token

router = APIRouter(prefix='/api/guild')


@router.get("/{guild_id}/settings")
async def get_guild(guild_id: int, user_id: int = Depends(get_user_id_from_access_token)):
    guild = Guild.get(guild_id)
    user = guild.guild.get_member(int(user_id))
    if not (user.guild_permissions.administrator or user.guild_permissions.manage_guild):
        raise Unauthorized

    guild_settings = guild.to_json()
    guild_settings['guild_roles'] = [
        {'id': str(role.id), 'name': role.name, 'color': hex(role.color.value), 'emoji': role.unicode_emoji}
        for role in guild.guild.roles
    ]
    guild_settings['guild_channels'] = guild.get_permitted_channels_json()

    return JSONResponse(guild_settings)
