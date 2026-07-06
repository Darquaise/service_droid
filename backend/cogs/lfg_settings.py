import discord
from discord.ext import commands

from classes import (
    ServiceDroid, ApplicationContext, Context, transform_time_lfg, LFGNotAllowed, build_command_listing_embed, option
)
from converters import TIME_UNITS


def generate_settings_embed(ctx: Context | ApplicationContext) -> discord.Embed:
    text = f"**LFG Channels**\n"
    if len(ctx.g.lfg_channels.values()) == 0:
        text += "None set"
    else:
        for lfg_channel in ctx.g.lfg_channels.values():
            text += f"\n{lfg_channel.channel.mention}: {''.join([role.mention for role in lfg_channel.roles])}"

    text += "\n\n**Host Roles**\n"
    if len(ctx.g.host_roles.values()) == 0:
        text += "None set"
    else:
        for role in ctx.g.host_roles.values():
            text += f"\n{role.role.mention}: {role.get_cooldown_text()}"

    embed = discord.Embed(
        title="LFG Settings",
        description=text,
        color=0xffd700
    )

    embed.set_author(name=f'{ctx.guild.name} - ID: {ctx.guild.id}')
    icon = ctx.guild.icon
    if icon:
        embed.set_thumbnail(url=icon.url)
    return embed


class LFGSettingsCog(discord.Cog):
    def __init__(self, bot: ServiceDroid):
        self.bot = bot

    @discord.slash_command(description="Change the amount of cooldown a Host has after a looking for game request")
    @discord.default_permissions(administrator=True)
    async def setting_set_host(
            self,
            ctx: ApplicationContext,
            role: discord.Role = option(discord.Role, "Host role the cooldown applies to"),
            time_unit: str = option(str, "Of what kind the given time will be", choices=TIME_UNITS),
            time_amount: int = option(int, "The amount of time"),
    ):
        # for some reason this is a string and not int
        time_amount = int(time_amount)

        if role.id in ctx.g.host_roles:
            old_time = ctx.g.host_roles[role.id].cooldown
        else:
            old_time = None
        new_time = transform_time_lfg(time_amount, time_unit)

        if new_time == old_time:
            return await ctx.respond(
                f"The cooldown has been set to {time_amount} {time_unit}. Nothing changed.",
                ephemeral=True
            )
        else:
            await ctx.g.set_cooldown(role, time_amount, time_unit)
            if isinstance(new_time, LFGNotAllowed):
                return await ctx.respond(
                    f"{role.mention} now can't use LFG commands anymore as long as this role is the highest Host Role the member has.",
                    ephemeral=True
                )

            return await ctx.respond(
                f"The cooldown for {role.mention} has been set to {time_amount} {time_unit}.",
                ephemeral=True
            )

    @discord.slash_command(description="Removes a Host Role")
    @discord.default_permissions(administrator=True)
    async def setting_remove_host(
            self, ctx: ApplicationContext,
            role: discord.Role = option(discord.Role, "Host role to remove"),
    ):
        if role.id not in ctx.g.host_roles.keys():
            return await ctx.respond(
                f"{role.mention} is no Host Role!",
                ephemeral=True
            )

        await ctx.g.remove_host_role(role.id)

        return await ctx.respond(
            f"{role.mention} isn't a Host Role anymore.",
            ephemeral=True
        )

    @discord.slash_command(
        description="Add LFG Roles to a channel. If the channel wasn't a LFG Channel before it will be made one."
    )
    @discord.default_permissions(administrator=True)
    async def setting_add_lfg(
            self,
            ctx: ApplicationContext,
            channel: discord.TextChannel = option(discord.TextChannel, "Channel that should accept /lfg"),
            role: discord.Role = option(discord.Role, "Role to be mentioned by /lfg in this channel"),
    ):
        was_present = channel.id in ctx.g.lfg_channels
        added = await ctx.g.add_lfg_role(channel, role)
        if not added:
            return await ctx.respond(
                f"{role.mention} is already being mentioned on LFG in {channel.mention}!",
                ephemeral=True
            )

        if was_present:
            return await ctx.respond(
                f"{role.mention} has been added to {channel.mention}\n"
                "Roles now being mentioned in this channel: "
                f"{' '.join(ctx.lfg.roles_str)}",
                ephemeral=True
            )
        return await ctx.respond(
            f"{channel.mention} is now a LFG Channel with the {role.mention} role being mentioned.\n"
            f"To add more use the same command with the same channel selected, but a different role.",
            ephemeral=True
        )

    @discord.slash_command(description="Remove a LFG Channel.")
    @discord.default_permissions(administrator=True)
    async def setting_remove_lfg(
            self, ctx: ApplicationContext,
            channel: discord.TextChannel = option(discord.TextChannel, "LFG channel to remove"),
    ):
        if channel.id in ctx.g.lfg_channels:
            await ctx.g.remove_lfg_channel(channel.id)
            await ctx.respond(
                f"{channel.mention} is no longer a LFG Channel.",
                ephemeral=True
            )
        else:
            await ctx.respond(
                f"{channel.mention} is no LFG Channel!",
                ephemeral=True
            )

    @discord.slash_command(description="See how things are set up currently")
    @discord.default_permissions(administrator=True)
    async def current_settings_lfg(self, ctx: ApplicationContext):
        embed = generate_settings_embed(ctx)
        await ctx.respond(embed=embed)

    @commands.command(name="current_settings_owner", hidden=True)
    @commands.is_owner()
    async def current_settings_lfg_owner(self, ctx: Context):
        embed = generate_settings_embed(ctx)
        await ctx.reply(embed=embed)

    @discord.slash_command(description="List LFG-Setting commands.")
    @discord.default_permissions(administrator=True)
    async def commands_lfg(self, ctx: ApplicationContext):
        embed = await build_command_listing_embed(
            self.bot, ctx.guild, "LFG commands", (LFGSettingsCog,),
        )
        await ctx.respond(embed=embed, ephemeral=True)
