from datetime import timedelta
import discord

from classes import ServiceDroid, ApplicationContext, build_command_listing_embed, option
from cogs.galatron_commands import TextGenerator
from converters.time import td2text_long, TIME_UNITS


def generate_settings_embed(ctx: ApplicationContext) -> discord.Embed:
    text = f"**Galatron Channels**\n"
    if len(ctx.g.galatron_channels) == 0:
        text += "None set"
    else:
        text += ", ".join([ga_channel.mention for ga_channel in ctx.g.galatron_channels])

    text += f"\n\n**Role:** {ctx.galatron.role.mention if ctx.galatron.role else None}\n"
    text += f"**Cooldown:** {td2text_long(ctx.g.galatron_cooldown)}\n"
    text += f"**Chance:** {ctx.g.galatron_chance * 100}%\n"

    embed = discord.Embed(
        title="Galatron Settings",
        description=text,
        color=0xffd700
    )

    embed.set_author(name=f'{ctx.guild.name} - ID: {ctx.guild.id}')
    icon = ctx.guild.icon
    if icon:
        embed.set_thumbnail(url=icon.url)
    return embed


class GalatronSettingsCog(discord.Cog):
    def __init__(self, bot: ServiceDroid):
        self.bot = bot

    @discord.slash_command(description="Allow members to hunt the Galatron in this channel.")
    @discord.default_permissions(administrator=True)
    async def setting_add_galatron_channel(
            self, ctx: ApplicationContext,
            channel: discord.TextChannel = option(discord.TextChannel, "Channel to enable the Galatron hunt in"),
    ):
        if channel in ctx.g.galatron_channels:
            return await ctx.respond(
                f"{channel.mention} is already being used for the Galatron hunt!",
                ephemeral=True
            )

        await ctx.g.add_galatron_channel(channel)

        return await ctx.respond(
            f"{channel.mention} is now viable for the Galatron hunt!.",
            ephemeral=True
        )

    @discord.slash_command(description="Stop allowing the Galatron hunt in this channel.")
    @discord.default_permissions(administrator=True)
    async def setting_remove_galatron_channel(
            self, ctx: ApplicationContext,
            channel: discord.TextChannel = option(discord.TextChannel, "Channel to disable the Galatron hunt in"),
    ):
        if channel in ctx.g.galatron_channels:
            await ctx.g.remove_galatron_channel(channel)

        return await ctx.respond(
            f"{channel.mention} is not being used for the Galatron hunt!",
            ephemeral=True
        )

    @discord.slash_command(description="Set the role granted to the current bearer of the Galatron.")
    @discord.default_permissions(administrator=True)
    async def setting_set_galatron_role(
            self, ctx: ApplicationContext,
            role: discord.Role = option(discord.Role, "Role assigned to whoever currently holds the Galatron"),
    ):
        if ctx.g.galatron_role and role.id == ctx.g.galatron_role.id:
            return await ctx.respond(f"{role.mention} is already being used for the Galatron hunt!")
        await ctx.g.set_galatron_role(role)
        return await ctx.respond(f"{role.mention} is now being used for the Galatron hunt!")

    @discord.slash_command(description="Set the per-member cooldown between Galatron attempts.")
    @discord.default_permissions(administrator=True)
    async def setting_set_galatron_cooldown(
            self, ctx: ApplicationContext,
            time_unit: str = option(str, "Of what kind the given time will be", choices=TIME_UNITS),
            time_amount: int = option(int, "The amount of time")
    ):
        # for some reason this is a string and not int
        time_amount = int(time_amount)

        if time_amount <= 0:
            return await ctx.respond(
                "The cooldown must be greater than 0.",
                ephemeral=True
            )

        # time_unit is restricted by choices=TIME_UNITS, all of which are valid timedelta kwargs
        duration = timedelta(**{time_unit: time_amount})

        if duration == ctx.g.galatron_cooldown:
            return await ctx.respond(
                f"The cooldown has been set to {time_amount} {time_unit}. Nothing changed.",
                ephemeral=True
            )
        else:
            await ctx.g.set_galatron_cooldown(duration)

            return await ctx.respond(
                f"The cooldown for the Galatron has been set to {time_amount} {time_unit}.",
                ephemeral=True
            )

    @discord.slash_command(description="Set the success chance per Galatron attempt.")
    @discord.default_permissions(administrator=True)
    async def setting_set_galatron_chance(
            self, ctx: ApplicationContext,
            chance: float = option(float, "Success chance in percent (0-100)"),
    ):
        if not 0 <= chance <= 100:
            return await ctx.respond(
                f"Chance must be between 0 and 100 (got {chance}).",
                ephemeral=True,
            )

        new_chance = chance / 100

        if new_chance == ctx.g.galatron_chance:
            return await ctx.respond(f"{chance}% chance is already being used for the Galatron hunt!")

        await ctx.g.set_galatron_chance(new_chance)

        return await ctx.respond(f"{chance}% chance is now being used for the Galatron hunt!")

    @discord.slash_command(description="See how things are set up currently")
    @discord.default_permissions(administrator=True)
    async def current_settings_galatron(self, ctx: ApplicationContext):
        embed = generate_settings_embed(ctx)
        await ctx.respond(embed=embed)

    @discord.slash_command(description="Forcefully reassign the Galatron to another member.")
    @discord.default_permissions(administrator=True)
    async def setting_set_galatron_owner(
            self,
            ctx: ApplicationContext,
            member: discord.Member = option(discord.Member, "The new bearer of the Galatron"),
    ):
        if not ctx.galatron.role:
            return await ctx.respond(
                "This feature hasn't been set up by your admins yet.",
                ephemeral=True,
            )

        history = ctx.g.galatron_history.history
        last_id = history[-1]["member_id"] if history else None

        if last_id == member.id:
            return await ctx.respond(
                embed=discord.Embed(
                    title=TextGenerator.title_decree(),
                    description=TextGenerator.admin_transfer_same(member.mention),
                    color=discord.Color.dark_purple(),
                ),
                ephemeral=True,
            )

        old_owner = ctx.galatron.current_owner
        reason = f"Galatron reassigned by admin {ctx.author}"

        try:
            await member.add_roles(ctx.galatron.role, reason=reason)
        except discord.Forbidden:
            return await ctx.respond(
                "Missing permissions to assign the Galatron role. "
                "Ensure the bot's top role is above the Galatron role.",
                ephemeral=True,
            )
        except discord.HTTPException as e:
            return await ctx.respond(f"Failed to assign role: `{e}`", ephemeral=True)

        if old_owner:
            try:
                await old_owner.remove_roles(ctx.galatron.role, reason=reason)
            except discord.HTTPException:
                pass

        await ctx.g.galatron_increment_total(member)
        await ctx.g.galatron_add_win(member)

        embed = discord.Embed(
            title=TextGenerator.title_decree(),
            description=TextGenerator.admin_transfer(
                member.mention,
                old_owner.mention if old_owner else None,
            ),
            color=discord.Color.dark_purple(),
        )

        announced = 0
        for channel in ctx.g.galatron_channels:
            try:
                await channel.send(embed=embed)
                announced += 1
            except discord.HTTPException:
                pass

        if announced == 0:
            return await ctx.respond(embed=embed)

        return await ctx.respond(
            f"Decree issued. {member.mention} now bears the Galatron "
            f"(announced in {announced} channel{'s' if announced != 1 else ''}).",
            ephemeral=True,
        )

    @discord.slash_command(description="Wipe all Galatron history, last-used and total-uses data.")
    @discord.default_permissions(administrator=True)
    async def galatron_reset(self, ctx: ApplicationContext):
        await ctx.g.galatron_reset()
        return await ctx.respond("Galatron reset complete!")

    @discord.slash_command(description="List Galatron-Setting commands.")
    @discord.default_permissions(administrator=True)
    async def commands_galatron(self, ctx: ApplicationContext):
        embed = await build_command_listing_embed(
            self.bot, ctx.guild, "Galatron commands", (GalatronSettingsCog,),
        )
        await ctx.respond(embed=embed, ephemeral=True)
