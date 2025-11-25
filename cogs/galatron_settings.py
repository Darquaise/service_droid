import discord
from discord.ext import commands

from classes import ServiceDroid, ApplicationContext, Context
from converters.time import td2text, TIME_UNITS, transform_time


def generate_settings_embed(ctx: Context | ApplicationContext) -> discord.Embed:
    text = f"**Galatron Channels**\n"
    if len(ctx.g.galatron_channels) == 0:
        text += "None set"
    else:
        text += ", ".join([ga_channel.mention for ga_channel in ctx.g.galatron_channels])

    text += f"\n\n**Role:** {ctx.galatron.role.mention if ctx.galatron.role else None}\n"
    text += f"**Cooldown:** {td2text(ctx.g.galatron_cooldown)}\n"
    text += f"**Chance:** {ctx.g.galatron_chance * 100}%\n"

    embed = discord.Embed(
        title="LFG Settings",
        description=text,
        color=0xffd700
    )

    embed.set_author(name=f'{ctx.guild.name} - ID: {ctx.guild.id}')
    embed.set_thumbnail(url=ctx.guild.icon.url)
    return embed


class GalatronSettingsCog(discord.Cog):
    def __init__(self, bot: ServiceDroid):
        self.bot = bot

    @discord.slash_command()
    @discord.default_permissions(administrator=True)
    async def setting_add_galatron_channel(self, ctx: ApplicationContext, channel: discord.TextChannel):
        if channel in ctx.g.galatron_channels:
            return await ctx.respond(
                f"{channel.mention} is already being used for the Galatron hunt!",
                ephemeral=True
            )

        ctx.g.galatron_channels.append(channel)
        self.bot.settings.update_guilds()

        return await ctx.respond(
            f"{channel.mention} is now viable for the Galatron hunt!.",
            ephemeral=True
        )

    @discord.slash_command()
    @discord.default_permissions(administrator=True)
    async def setting_remove_galatron_channel(self, ctx: ApplicationContext, channel: discord.TextChannel):
        if channel in ctx.g.galatron_channels:
            ctx.g.galatron_channels.remove(channel)
            self.bot.settings.update_guilds()

        return await ctx.respond(
            f"{channel.mention} is not being used for the Galatron hunt!",
            ephemeral=True
        )

    @discord.slash_command()
    @discord.default_permissions(administrator=True)
    async def setting_set_galatron_role(self, ctx: ApplicationContext, role: discord.Role):
        if role.id == ctx.g.galatron_role.id if ctx.g.galatron_role else None:
            return await ctx.respond(f"{role.mention} is already being used for the Galatron hunt!")
        ctx.g.galatron_role = role
        self.bot.settings.update_guilds()
        return await ctx.respond(f"{role.mention} is now being used for the Galatron hunt!")

    @discord.slash_command()
    @discord.default_permissions(administrator=True)
    async def setting_set_galatron_cooldown(
            self, ctx: ApplicationContext,
            time_unit: discord.Option(str, "Of what kind the given time will be", choices=TIME_UNITS),
            time_amount: discord.Option(int, "The amount of time")
    ):
        # for some reason this is a string and not int
        time_amount = int(time_amount)

        duration = transform_time(time_amount, time_unit)

        if duration == ctx.g.galatron_cooldown:
            return await ctx.respond(
                f"The cooldown has been set to {time_amount} {time_unit}. Nothing changed.",
                ephemeral=True
            )
        else:
            ctx.g.galatron_cooldown = duration
            self.bot.settings.update_guilds()

            return await ctx.respond(
                f"The cooldown for the Galatron has been set to {time_amount} {time_unit}.",
                ephemeral=True
            )

    @discord.slash_command()
    @discord.default_permissions(administrator=True)
    async def setting_set_galatron_chance(self, ctx: ApplicationContext, chance: float):
        print("raw", chance)
        chance /= 100
        print("chance", chance)
        print("old chance", ctx.g.galatron_chance)
        if chance == ctx.g.galatron_chance:
            return await ctx.respond(f"{chance} is already being used for the Galatron hunt!")

        ctx.g.galatron_chance = chance
        self.bot.settings.update_guilds()

        return await ctx.respond(f"{chance}% chance is now being used for the Galatron hunt!")

    @discord.slash_command(description="See how things are set up currently")
    @discord.default_permissions(administrator=True)
    async def current_settings_galatron(self, ctx: ApplicationContext):
        embed = generate_settings_embed(ctx)
        await ctx.respond(embed=embed)

    @commands.command(name="current_settings_galatron_owner", hidden=True)
    @commands.is_owner()
    async def current_settings_galatron_owner(self, ctx: Context):
        embed = generate_settings_embed(ctx)
        await ctx.reply(embed=embed)
