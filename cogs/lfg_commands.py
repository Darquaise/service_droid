import discord
from discord.ext import commands
from datetime import datetime

from classes import ServiceDroid, Context, ApplicationContext, Guild, LFGNotAllowed
from converters import dt_now_as_text


class LFGCog(discord.Cog):
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
            return datetime.now()

    def set_cooldown(self, member: discord.Member):
        if member.guild.id not in self.cooldowns:
            self.cooldowns[member.guild.id] = {}

        self.cooldowns[member.guild.id][member.id] = datetime.now()

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
        if next_use > datetime.now():
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

    @discord.slash_command(name="lfg", description="Ask others to join your gaming endeavour")
    async def lfg_slash(self, ctx: ApplicationContext, message: str = None):
        assert isinstance(ctx.author, discord.Member)

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
        if next_use > datetime.now():
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
        return None

    @discord.slash_command(
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


def setup(bot):
    bot.add_cog(CustomCog(bot))
