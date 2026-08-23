from __future__ import annotations

import logging
import time
import discord

logger = logging.getLogger(__name__)

DISSOLVE_AFTER_PERM_FAILS = 3
NOTIFY_REPEAT_AFTER = 6 * 3600

PERM_LABELS: dict[str, str] = {
    "view_channel": "View Channel",
    "send_messages": "Send Messages",
    "embed_links": "Embed Links",
    "manage_channels": "Manage Channels",
    "manage_roles": "Manage Roles",
    "mention_everyone": "Mention @everyone, @here and All Roles",
}


def missing_channel_perms(
        channel: discord.abc.GuildChannel, *needed: str
) -> list[str]:
    perms = channel.permissions_for(channel.guild.me)
    return [PERM_LABELS.get(p, p) for p in needed if not getattr(perms, p)]


def format_missing_perms(channel: discord.abc.GuildChannel, missing: list[str]) -> str:
    perms = ", ".join(f"**{m}**" for m in missing)
    many = len(missing) != 1
    return (
        f"I'm missing the following permission{'s' if many else ''} in {channel.mention}: {perms}.\n"
        f"Grant {'them' if many else 'it'} and run the command again."
    )


def role_assignment_error(guild: discord.Guild, role: discord.Role) -> str | None:
    """Message explaining why the bot can't assign/remove ``role``, or None if it can."""
    me = guild.me
    if not me.guild_permissions.manage_roles:
        return "I need the **Manage Roles** permission to hand out this role."
    if role.is_default():
        return "The @everyone role can't be used here."
    if role.managed:
        return f"{role.mention} is managed by an integration and can't be assigned manually."
    if role >= me.top_role:
        return (
            f"{role.mention} is above (or equal to) my highest role, so I can't assign it. "
            f"Move my role above {role.mention} in Server Settings → Roles."
        )
    return None


def role_ping_warning(channel: discord.abc.GuildChannel, role: discord.Role) -> str | None:
    """Warning if pinging ``role`` in ``channel`` wouldn't notify anyone, else None."""
    if role.mentionable:
        return None
    if channel.permissions_for(channel.guild.me).mention_everyone:
        return None
    return (
        f"⚠️ {role.mention} isn't mentionable and I lack "
        f"**{PERM_LABELS['mention_everyone']}** in {channel.mention}, so pinging it won't "
        f"notify anyone. Make the role mentionable or grant me that permission."
    )


_notified: dict[int, dict[str, float]] = {}


def _is_repeat(guild_id: int, message: str) -> bool:
    """True if this exact message already went to that guild within NOTIFY_REPEAT_AFTER."""
    now = time.monotonic()
    seen = _notified.setdefault(guild_id, {})
    for text, sent_at in list(seen.items()):
        if now - sent_at >= NOTIFY_REPEAT_AFTER:
            del seen[text]
    if message in seen:
        return True
    # Recorded before the send, so a failing DM can't be retried into a spam loop either.
    seen[message] = now
    return False


async def notify_owner(guild: discord.Guild, message: str) -> bool:
    """Best-effort DM to the guild owner (prefixed with the guild name). Returns success.

    Repeats of the same message are dropped; a different warning still gets through.
    """
    if _is_repeat(guild.id, message):
        logger.debug("guild %s: skipping repeated owner notice: %s", guild.id, message)
        return False
    owner = guild.owner
    if owner is None and guild.owner_id is not None:
        try:
            owner = await guild.fetch_member(guild.owner_id)
        except discord.HTTPException:
            owner = None
    if owner is None:
        logger.warning("guild %s: no reachable owner to notify: %s", guild.id, message)
        return False
    try:
        await owner.send(f"**{guild.name}**\n{message}")
        return True
    except discord.HTTPException:
        logger.warning("guild %s: could not DM owner: %s", guild.id, message)
        return False
