from fastapi import APIRouter, Depends, Request
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
    guild_settings['guild_roles'] = guild.get_roles_json()
    guild_settings['guild_channels'] = guild.get_permitted_channels_json()

    return JSONResponse(guild_settings)


@router.get("/{guild_id}/delete_lfg_role")
async def delete_lfg_role(request: Request, guild_id: int, channel_id: int, role_id: int,
                          user_id: int = Depends(get_user_id_from_access_token)):
    guild = Guild.get(guild_id)
    user = guild.guild.get_member(int(user_id))
    if not (user.guild_permissions.administrator or user.guild_permissions.manage_guild):
        raise Unauthorized

    print('auth')

    if channel_id in guild.lfg_channels:
        print('channel found')
        channel = guild.lfg_channels[channel_id]
        if channel.remove_role(role_id):
            print('role found')
            request.app.bot.settings.update_settings()
            return JSONResponse({'successful': True})

    return JSONResponse({'successful': False})
