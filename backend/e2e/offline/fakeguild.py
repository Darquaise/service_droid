"""A guild that exists only in memory, for harness self-tests that need no Discord."""

from __future__ import annotations

import discord

GUILD_ID = 8000000000000000001
BOT_ID = 8000000000000000002
ADMIN_ID = 8000000000000000003
PLAYER_ID = 8000000000000000004
GENERAL_ID = 8000000000000000010
QUIET_ID = 8000000000000000011
ADMIN_ROLE_ID = 8000000000000000020
BOT_ROLE_ID = 8000000000000000021
COLORS = {"primary_color": 0, "secondary_color": None, "tertiary_color": None}


def _user(uid: int, name: str, bot: bool) -> dict:
    return {
        "id": str(uid), "username": name, "discriminator": "0", "global_name": name,
        "avatar": None, "bot": bot,
    }


def build(bot: discord.Client) -> discord.Guild:
    state = bot._connection
    state.user = discord.ClientUser(state=state, data={**_user(BOT_ID, "droid", True), "verified": True})
    everyone = {
        "id": str(GUILD_ID), "name": "@everyone", "permissions": str(
            discord.Permissions(view_channel=True, send_messages=True, embed_links=True, attach_files=True).value
        ),
        "position": 0, "color": 0, "colors": COLORS, "hoist": False, "managed": False, "mentionable": False,
    }
    admin_role = {
        "id": str(ADMIN_ROLE_ID), "name": "admin", "permissions": str(discord.Permissions(administrator=True).value),
        "position": 1, "color": 0, "colors": COLORS, "hoist": False, "managed": False, "mentionable": False,
    }
    bot_role = {
        "id": str(BOT_ROLE_ID), "name": "droid", "permissions": str(discord.Permissions(administrator=True).value),
        "position": 5, "color": 0, "colors": COLORS, "hoist": False, "managed": True, "mentionable": False,
    }

    def member(uid: int, name: str, roles: list[int], is_bot: bool) -> dict:
        return {
            "user": _user(uid, name, is_bot), "roles": [str(r) for r in roles], "nick": None,
            "joined_at": "2026-01-01T00:00:00+00:00", "deaf": False, "mute": False, "flags": 0,
        }

    quiet_overwrite = {
        "id": str(BOT_ID), "type": 1, "allow": "0", "deny": str(discord.Permissions(attach_files=True).value),
    }
    data = {
        "id": str(GUILD_ID), "name": "e2e offline", "owner_id": str(ADMIN_ID), "roles": [everyone, admin_role, bot_role],
        "channels": [
            {"id": str(GENERAL_ID), "type": 0, "name": "general", "position": 0, "permission_overwrites": []},
            {"id": str(QUIET_ID), "type": 0, "name": "quiet", "position": 1, "permission_overwrites": [quiet_overwrite]},
        ],
        "members": [
            member(BOT_ID, "droid", [BOT_ROLE_ID], True),
            member(ADMIN_ID, "admin", [ADMIN_ROLE_ID], True),
            member(PLAYER_ID, "player", [], True),
        ],
        "member_count": 3, "emojis": [], "stickers": [], "features": [], "threads": [],
        "voice_states": [], "presences": [],
    }
    return state._add_guild_from_data(data)
