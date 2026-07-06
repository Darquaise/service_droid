from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from store import load_guild_state, trivia_repo

from .guild import Guild
from .trivia import TriviaHandler

if TYPE_CHECKING:
    from .bot import ServiceDroid

logger = logging.getLogger(__name__)


async def reload_guild(bot: "ServiceDroid", guild_id: int) -> bool:
    """Re-read one guild from the database and rebuild its in-memory objects:
    the ``Guild`` aggregate, its ``TriviaHandler``, and the trivia scheduler for
    its channels. Returns ``False`` if the bot isn't in that guild.
    """
    discord_guild = bot.get_guild(guild_id)
    if discord_guild is None:
        return False

    gs, trivia_lists = await load_guild_state(guild_id)

    previous = Guild.get(guild_id)
    old_channels = set(previous.trivia_channels) if previous else set()
    old_mc_channels = set(previous.minecraft_channels) if previous else set()

    Guild.from_state(discord_guild, gs)  # overwrites the registry entry
    TriviaHandler.replace_for_guild(discord_guild, trivia_lists)

    scheduler = bot.trivia_scheduler
    current = Guild.get(guild_id)
    if scheduler is not None and current is not None:
        # Pending rows survive a cancel-while-waiting, so re-attach them to the
        # rebuilt configs and reschedule; channels that vanished get cancelled.
        pending = await trivia_repo.load_pending()
        for channel_id in old_channels - set(current.trivia_channels):
            scheduler.cancel_channel(channel_id)
        for channel_id, config in current.trivia_channels.items():
            raw = pending.get(str(channel_id))
            if raw is not None:
                config.pending = raw
            scheduler.schedule_channel(channel_id, config)

    updater = bot.minecraft_updater
    if updater is not None and current is not None:
        for channel_id in old_mc_channels - set(current.minecraft_channels):
            updater.cancel_channel(channel_id)
        for channel_id, config in current.minecraft_channels.items():
            updater.schedule_channel(channel_id, config)

    logger.info("reloaded guild %s from database", guild_id)
    return True
