import discord
from discord.ext import commands
from datetime import datetime

from classes.bot import ServiceDroid


class CustomCog(discord.Cog):
    def __init__(self, bot: ServiceDroid):
        self.bot = bot
        self.cooldowns: dict = {}

    @commands.command(name="lfg", aliases=["lgf"])
    async def lfg(self, ctx: commands.Context, *, message: str = None):
        # stop if not in the right channel
        if ctx.channel.id not in self.bot.settings.allowed_channels.keys():
            await ctx.message.delete()
            return

        lfg_roles = [ctx.guild.get_role(x).mention for x in self.bot.settings.allowed_channels[ctx.channel.id]]

        # check for cooldown and return if still on cooldown
        if ctx.author.id in self.cooldowns:
            next_use = self.cooldowns[ctx.author.id] + self.bot.settings.cooldown
            if next_use > datetime.utcnow():
                await ctx.reply(
                    content=f"You are still on cooldown, you can invite to a new game {discord.utils.format_dt(next_use, 'R')}",
                    delete_after=10
                )
                await ctx.message.delete()
                return

        # set cooldown, this is done before to prevent possible spam
        self.cooldowns[ctx.author.id] = datetime.utcnow()

        # send message with additional message if given
        lfg_msg = f"{ctx.author.mention} is looking for a game! {' '.join(lfg_roles)}\n"
        if message:
            await ctx.send(lfg_msg + discord.utils.escape_mentions(message))
        else:
            await ctx.send(lfg_msg)

        # delete casting message
        await ctx.message.delete()

    @discord.application_command(name="lfg", description="Ask others to join your gaming endeavour")
    async def lfg_slash(self, ctx: discord.ApplicationContext, message: str = None):
        # stop if not in the right channel
        if ctx.channel.id not in self.bot.settings.allowed_channels:
            return await ctx.respond(
                "This command isn't allowed here!",
                ephemeral=True
            )

        lfg_roles = [ctx.guild.get_role(x).mention for x in self.bot.settings.allowed_channels[ctx.channel.id]]

        if ctx.author.id in self.cooldowns:
            next_use = self.cooldowns[ctx.author.id] + self.bot.settings.cooldown
            if next_use > datetime.utcnow():
                return await ctx.respond(
                    f"You are still on cooldown, you can invite to a new game {discord.utils.format_dt(next_use, 'R')}",
                    ephemeral=True
                )

        # set cooldown, this is done before to prevent possible spam
        self.cooldowns[ctx.author.id] = datetime.utcnow()

        # create a reply so it won't time out
        msg = await ctx.respond("Your invite will be sent shortly after", ephemeral=True)

        lfg_msg = f"{ctx.author.mention} is looking for a game! {' '.join(lfg_roles)}\n"
        if message:
            await ctx.send(lfg_msg + discord.utils.escape_mentions(message))
        else:
            await ctx.send(lfg_msg)

        # deleting reply
        if msg:
            await ctx.delete()

    @discord.application_command(
        description="Reset the looking for game cooldown for everyone or a chosen member"
    )
    @discord.default_permissions(administrator=True)
    async def reset_cooldown(self, ctx: discord.ApplicationContext, member: discord.Member = None):
        if member:
            if member.id in self.cooldowns:
                del self.cooldowns[member.id]
                await ctx.respond(
                    f"The cooldown for {member.mention} has been reset!",
                    ephemeral=True
                )
            else:
                await ctx.respond(
                    "This member isn't on cooldown",
                    ephemeral=True
                )
        else:
            self.cooldowns = {}
            await ctx.respond(
                "All cooldowns have been reset!",
                ephemeral=True
            )
