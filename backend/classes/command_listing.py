from __future__ import annotations

import discord


async def build_command_listing_embed(
        bot: discord.Bot, guild: discord.Guild, title: str, cog_classes: tuple[type, ...],
) -> discord.Embed:
    selected: dict[str, discord.SlashCommand] = {}
    for c in bot.application_commands:
        if isinstance(c, discord.SlashCommand) and c.cog is not None and isinstance(c.cog, cog_classes):
            selected[c.name] = c

    id_by_name: dict[str, int] = {}
    try:
        registered = await bot.http.get_guild_commands(bot.user.id, guild.id)
        id_by_name = {r["name"]: int(r["id"]) for r in registered}
    except discord.HTTPException:
        pass

    if not selected:
        description = "No commands registered yet."
    else:
        lines = []
        for name in sorted(selected):
            c = selected[name]
            cid = id_by_name.get(name, c.id)
            mention = f"</{name}:{cid}>" if cid else f"/{name}"
            lines.append(f"{mention} — {c.description or '*(no description)*'}")
        description = "\n".join(lines)
    return discord.Embed(title=title, description=description, colour=0xffd700)
