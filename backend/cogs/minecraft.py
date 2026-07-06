import logging
import discord
from discord.ext import commands

from classes import (
    ServiceDroid, ApplicationContext, Guild, MinecraftStatusConfig, MinecraftStatusUpdater,
    build_command_listing_embed, fetch_player_count, option,
)

logger = logging.getLogger(__name__)


class MinecraftCog(commands.Cog):
    def __init__(self, bot: ServiceDroid):
        self.bot = bot
        self.updater = MinecraftStatusUpdater(bot)
        bot.minecraft_updater = self.updater
        bot.loop.create_task(self._initial_schedule())

    # noinspection PyBroadException
    async def _initial_schedule(self):
        try:
            await self.bot.wait_until_ready()
            for guild in Guild.get_all():
                for cid, cfg in guild.minecraft_channels.items():
                    self.updater.schedule_channel(cid, cfg)
        except Exception:
            logger.exception("initial minecraft status scheduling failed")

    def cog_unload(self):
        self.updater.cancel_all()

    @discord.slash_command(
        description="Show a Minecraft server's status (online count) in a voice channel's name."
    )
    @discord.default_permissions(administrator=True)
    async def setting_minecraft_set_channel(
            self, ctx: ApplicationContext,
            channel: discord.VoiceChannel = option(
                discord.VoiceChannel, "Voice channel whose name mirrors the server status"),
            address: str = option(str, "Server address, e.g. `mc.example.com` or `host:25565`"),
    ):
        address = address.strip()
        if not address:
            return await ctx.respond("The server address must not be empty.", ephemeral=True)

        await ctx.defer(ephemeral=True)
        online = await fetch_player_count(address)

        config = MinecraftStatusConfig(channel.id, address)
        await ctx.g.set_minecraft_channel(config)
        self.updater.schedule_channel(channel.id, config)

        reachable = (
            f"Currently reachable with **{online}** player(s) online."
            if online is not None
            else "Currently **not reachable** — the channel will show Offline until it responds."
        )
        return await ctx.respond(
            f"{channel.mention} now mirrors the status of `{address}`.\n"
            f"{reachable}\n"
            f"Updates run every ~5 minutes (Discord limits channel renames to 2 per 10 minutes).",
            ephemeral=True,
        )

    @discord.slash_command(description="Stop mirroring a Minecraft server in a voice channel.")
    @discord.default_permissions(administrator=True)
    async def setting_minecraft_remove_channel(
            self, ctx: ApplicationContext,
            channel: discord.VoiceChannel = option(
                discord.VoiceChannel, "Voice channel to stop updating"),
    ):
        guild = ctx.g
        if channel.id not in guild.minecraft_channels:
            return await ctx.respond(
                f"{channel.mention} is not mirroring a Minecraft server.", ephemeral=True
            )
        await guild.remove_minecraft_channel(channel.id)
        self.updater.cancel_channel(channel.id)
        return await ctx.respond(
            f"{channel.mention} no longer mirrors a Minecraft server. "
            f"The channel name stays as it is — rename it manually if needed.",
            ephemeral=True,
        )

    @discord.slash_command(description="Show all voice channel → Minecraft server mappings.")
    @discord.default_permissions(administrator=True)
    async def setting_minecraft_show_mappings(self, ctx: ApplicationContext):
        guild = ctx.g
        if not guild.minecraft_channels:
            return await ctx.respond("No Minecraft status channels have been set yet.", ephemeral=True)

        lines = [f"<#{cid}> → `{cfg.address}`" for cid, cfg in guild.minecraft_channels.items()]
        embed = discord.Embed(
            title="Minecraft status channels", description="\n".join(lines), color=0x2ecc71
        )
        return await ctx.respond(embed=embed, ephemeral=True)

    @discord.slash_command(description="List Minecraft-Setting commands.")
    @discord.default_permissions(administrator=True)
    async def commands_minecraft(self, ctx: ApplicationContext):
        embed = await build_command_listing_embed(
            self.bot, ctx.guild, "Minecraft commands", (MinecraftCog,),
        )
        await ctx.respond(embed=embed, ephemeral=True)
