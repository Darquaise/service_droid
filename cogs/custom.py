import discord
from discord.ext import commands
from datetime import datetime

from classes import ServiceDroid, Context, ApplicationContext, Guild, LFGNotAllowed
from converters import dt_now_as_text, utcnow


class CustomCog(discord.Cog):
    def __init__(self, bot: ServiceDroid):
        self.bot = bot
        self.cooldowns: dict[int, dict[int, datetime]] = {}

    def next_lfg_use(self, member: discord.Member) -> datetime | type[LFGNotAllowed]:
        cooldown = Guild.get(member.guild.id).get_member_cooldown(member)

        if cooldown is LFGNotAllowed:
            return LFGNotAllowed

        if member.guild.id not in self.cooldowns:
            self.cooldowns[member.guild.id] = {}

        if member.id in self.cooldowns[member.guild.id]:
            return self.cooldowns[member.guild.id][member.id] + cooldown
        else:
            return utcnow()

    def set_cooldown(self, member: discord.Member):
        if member.guild.id not in self.cooldowns:
            self.cooldowns[member.guild.id] = {}

        self.cooldowns[member.guild.id][member.id] = utcnow()

    @commands.command(name="lfg", aliases=["lgf"])
    async def lfg(self, ctx: Context, *, message: str = None):
        # stop if not in the right channel
        if not ctx.lfg.is_lfg_channel:
            if ctx.own_perms.manage_messages:
                await ctx.message.delete()
            return

        next_use = self.next_lfg_use(ctx.author)

        # check if user is allowed to use
        if next_use is LFGNotAllowed:
            return

        # check for cooldown and return if still on cooldown
        if next_use > utcnow():
            await ctx.reply(
                content=f"You are still on cooldown, you can invite to a new game {discord.utils.format_dt(next_use, 'R')}",
                delete_after=10
            )
            await ctx.message.delete()
            return

        # set cooldown, this is done before to prevent possible spam
        self.set_cooldown(ctx.author)

        # send message with additional message if given
        lfg_msg = f"{ctx.author.mention} is looking for a game! {' '.join(ctx.lfg.roles_str)}\n"
        if message:
            await ctx.send(lfg_msg + discord.utils.escape_mentions(message))  # TODO: check if message is too long
        else:
            await ctx.send(lfg_msg)

        # delete casting message
        await ctx.message.delete()

    @discord.application_command(name="lfg", description="Ask others to join your gaming endeavour")
    async def lfg_slash(self, ctx: ApplicationContext, message: str = None):
        # fix for linter not liking properties
        ctx.author: discord.Member  # type: ignore

        # stop if not in the right channel
        if not ctx.lfg.is_lfg_channel:
            return await ctx.respond(
                "This command isn't allowed here!",
                ephemeral=True
            )

        next_use = self.next_lfg_use(ctx.author)

        # check if user is allowed to use
        if next_use is LFGNotAllowed:
            return await ctx.respond(
                "You don't posses any roles allowing the casting of the LFG command",
                ephemeral=True
            )

        # check for cooldown and return if still on cooldown
        if next_use > utcnow():
            return await ctx.respond(
                f"You are still on cooldown, you can invite to a new game {discord.utils.format_dt(next_use, 'R')}",
                ephemeral=True
            )

        # set cooldown, this is done before to prevent possible spam
        self.set_cooldown(ctx.author)

        # create a reply so it won't time out
        msg = await ctx.respond("Your invite will be sent shortly after", ephemeral=True)

        lfg_msg = f"{ctx.author.mention} is looking for a game! {' '.join(ctx.lfg.roles_str)}\n"
        if message:
            await ctx.send(lfg_msg + discord.utils.escape_mentions(message))  # TODO: check if message is too long
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
            if member.id in self.cooldowns[member.guild.id]:
                del self.cooldowns[member.guild.id][member.id]
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
            self.cooldowns[member.guild.id] = {}
            await ctx.respond(
                "All cooldowns have been reset!",
                ephemeral=True
            )
            print(f"[{dt_now_as_text()}] cooldowns of {member.guild.name} ({member.guild.id}) reset")

    @discord.application_command(
        description="See how things are set up currently"
    )
    @discord.default_permissions(administrator=True)
    async def current_settings(self, ctx: ApplicationContext):
        text = f"**Channels**\n"
        for channel in ctx.g.lfg_channels.values():
            text += f"\n{channel.channel.mention}: {''.join([role.mention for role in channel.roles])}"

        text += "\n\n**Roles**\n"
        for role in ctx.g.host_roles.values():
            text += f"\n{role.role.mention}: {role._amount} {role._unit}"  # noqa

        embed = discord.Embed(
            title="LFG Settings",
            description=text,
            color=0xffd700
        )

        embed.set_author(name=f'{ctx.guild.name} - ID: {ctx.guild.id}')
        embed.set_thumbnail(url=ctx.guild.icon.url)

        await ctx.respond(embed=embed)


def setup(bot):
    bot.add_cog(CustomCog(bot))
