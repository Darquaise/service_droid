from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from classes import Guild
from converters import transform_time

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


# !!! settings like turning off all commands are still missing

@router.get("/{guild_id}/add_lfg_channel")
async def add_lfg_channel(
        request: Request, guild_id: int, channel_id: int, role_id: int,
        user_id: int = Depends(get_user_id_from_access_token)
):
    guild = Guild.get(guild_id)
    user = guild.guild.get_member(int(user_id))
    if not (user.guild_permissions.administrator or user.guild_permissions.manage_guild):
        raise Unauthorized

    if channel_id in guild.lfg_channels.keys():
        return JSONResponse({'successful': False, 'message': 'Channel is a LFG Channel already'})

    channel = guild.guild.get_channel(channel_id)
    if not channel:
        return JSONResponse({'successful': False, 'message': 'Channel not found'})

    role = guild.guild.get_role(role_id)
    if not role:
        return JSONResponse({'successful': False, 'message': 'Role not found'})

    guild.add_lfg_channel(channel, [role])
    request.app.bot.settings.update_settings()
    return JSONResponse({'successful': True})


@router.get("/{guild_id}/delete_lfg_channel")
async def delete_lfg_channel(
        request: Request, guild_id: int, channel_id: int, user_id: int = Depends(get_user_id_from_access_token)
):
    guild = Guild.get(guild_id)
    user = guild.guild.get_member(int(user_id))
    if not (user.guild_permissions.administrator or user.guild_permissions.manage_guild):
        raise Unauthorized

    if channel_id in guild.lfg_channels.keys():
        del guild.lfg_channels[channel_id]
        request.app.bot.settings.update_settings()
        return JSONResponse({'successful': True})
    return JSONResponse({'successful': False, 'message': 'LFG Channel not found'})


@router.get("/{guild_id}/add_lfg_role")
async def add_lfg_role(
        request: Request, guild_id: int, channel_id: int, role_id: int,
        user_id: int = Depends(get_user_id_from_access_token)
):
    guild = Guild.get(guild_id)
    user = guild.guild.get_member(int(user_id))
    if not (user.guild_permissions.administrator or user.guild_permissions.manage_guild):
        raise Unauthorized

    if channel_id not in guild.lfg_channels.keys():
        return JSONResponse({'successful': False, 'message': 'LFG Channel not found'})

    role = guild.guild.get_role(role_id)
    if not role:
        return JSONResponse({'successful': False, 'message': 'Role not found'})

    guild.lfg_channels[channel_id].roles.append(role)
    request.app.bot.settings.update_settings()
    return JSONResponse({'successful': True})


@router.get("/{guild_id}/delete_lfg_role")
async def delete_lfg_role(
        request: Request, guild_id: int, channel_id: int, role_id: int,
        user_id: int = Depends(get_user_id_from_access_token)
):
    guild = Guild.get(guild_id)
    user = guild.guild.get_member(int(user_id))
    if not (user.guild_permissions.administrator or user.guild_permissions.manage_guild):
        raise Unauthorized

    if channel_id in guild.lfg_channels.keys():
        channel = guild.lfg_channels[channel_id]
        if channel.remove_role(role_id):
            request.app.bot.settings.update_settings()
            return JSONResponse({'successful': True})
        else:
            return JSONResponse({'successful': False, 'message': 'LFG Role not found'})

    return JSONResponse({'successful': False, 'message': 'LFG Channel not found'})


@router.get("/{guild_id}/add_host_role")
async def add_host_role(
        request: Request, guild_id: int, role_id: int, cooldown: int, cooldown_type: str,
        user_id: int = Depends(get_user_id_from_access_token)
):
    guild = Guild.get(guild_id)
    user = guild.guild.get_member(int(user_id))
    if not (user.guild_permissions.administrator or user.guild_permissions.manage_guild):
        raise Unauthorized

    if role_id in guild.host_roles.keys():
        return JSONResponse({'successful': False, 'message': 'Role is a host already'})

    role = guild.guild.get_role(role_id)
    if not role:
        return JSONResponse({'successful': False, 'message': 'Role not found'})

    time = transform_time(cooldown, cooldown_type)  # !!! permission removal not implemented yet
    if not time:
        return JSONResponse({'successful': False, 'message': 'Not a valid timeframe'})

    guild.set_cooldown(role, cooldown, cooldown_type)
    request.app.bot.settings.update_settings()

    return JSONResponse({'successful': True})


@router.get("/{guild_id}/edit_host_role")
async def edit_host_role(
        request: Request, guild_id: int, role_id: int, cooldown: int, cooldown_type: str,
        user_id: int = Depends(get_user_id_from_access_token)
):
    guild = Guild.get(guild_id)
    user = guild.guild.get_member(int(user_id))
    if not (user.guild_permissions.administrator or user.guild_permissions.manage_guild):
        raise Unauthorized

    if role_id not in guild.host_roles.keys():
        return JSONResponse({'successful': False, 'message': 'Host Role not found'})

    role = guild.guild.get_role(role_id)
    if not role:
        return JSONResponse({'successful': False, 'message': 'Role not found'})

    time = transform_time(cooldown, cooldown_type)  # !!! permission removal not implemented yet
    if not time:
        return JSONResponse({'successful': False, 'message': 'Not a valid timeframe'})

    guild.set_cooldown(role, cooldown, cooldown_type)
    request.app.bot.settings.update_settings()

    return JSONResponse({'successful': True})


@router.get("/{guild_id}/delete_host_role")
async def delete_host_role(
        request: Request, guild_id: int, role_id: int, user_id: int = Depends(get_user_id_from_access_token)
):
    guild = Guild.get(guild_id)
    user = guild.guild.get_member(int(user_id))
    if not (user.guild_permissions.administrator or user.guild_permissions.manage_guild):
        raise Unauthorized

    if role_id not in guild.host_roles.keys():
        return JSONResponse({'successful': False, 'message': 'Host Role not found'})

    del guild.host_roles[role_id]
    request.app.bot.settings.update_settings()

    return JSONResponse({'successful': True})
