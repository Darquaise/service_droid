import discord

from classes import ServiceDroid, ApplicationContext, transform_time, LFGNotAllowed

time_units = ["days", "hours", "minutes", "seconds"]


class SettingsCog(discord.Cog):
    def __init__(self, bot: ServiceDroid):
        self.bot = bot

    @discord.slash_command(name="turn_lfg_on_or_off", description="Turn Looking for game requests on or off")
    @discord.default_permissions(administrator=True)
    async def turn_lfg(self, ctx: ApplicationContext):
        self.bot.settings.active = not self.bot.settings.active
        self.bot.settings.update_settings()
        await ctx.respond(f"Looking for game command has be turned {'on' if self.bot.settings.active else 'off'}")

    @discord.slash_command(description="Change the amount of cooldown a Host has after a looking for game request")
    @discord.default_permissions(administrator=True)
    async def setting_set_host(
            self,
            ctx: ApplicationContext,
            role: discord.Role,
            time_unit: discord.Option(description="Of what kind the given time will be", choices=time_units),
            time_amount: discord.Option(name="amount", description="The amount of time", input_type=int)
    ):
        # for some reason this is a string and not int
        time_amount = int(time_amount)

        if role.id in ctx.g.host_roles:
            old_time = ctx.g.host_roles[role.id].cooldown
        else:
            old_time = None
        new_time = transform_time(time_amount, time_unit)

        if not new_time:
            return await ctx.respond(
                "This is not a valid time unit, the following are available: `days`, `hours`, `minutes`, `seconds`!",
                ephemeral=True
            )

        if new_time == old_time:
            await ctx.respond(
                f"The cooldown has been set to {time_amount} {time_unit}. Nothing changed.",
                ephemeral=True
            )
        else:
            ctx.g.set_cooldown(role, time_amount, time_unit)
            if isinstance(new_time, LFGNotAllowed):
                self.bot.settings.update_guilds()
                return await ctx.respond(
                    f"{role.mention} now can't use LFG commands anymore as long as this role is the highest Host Role the member has.",
                    ephemeral=True
                )

            await ctx.respond(
                f"The cooldown for {role.mention} has been set to {time_amount} {time_unit}.",
                ephemeral=True
            )
            self.bot.settings.update_guilds()

    @discord.slash_command(
        description="Add LFG Roles to a channel. If the channel wasn't a LFG Channel before it will be made one."
    )
    @discord.default_permissions(administrator=True)
    async def setting_add_lfg(
            self,
            ctx: ApplicationContext,
            channel: discord.TextChannel,
            role: discord.Role
    ):
        if channel.id in ctx.g.lfg_channels.keys():
            if role in ctx.lfg.roles:
                return await ctx.respond(
                    f"{role.mention} is already being mentioned on LFG in {channel.mention}!",
                    ephemeral=True
                )
            ctx.g.lfg_channels[channel.id].roles.append(role)
            await ctx.respond(
                f"{role.mention} has been added to {channel.mention}\n"
                "Roles now being mentioned in this channel: "
                f"{' '.join(ctx.lfg.roles_str)}",
                ephemeral=True
            )
        else:
            ctx.g.add_lfg_channel(channel, [role])
            await ctx.respond(
                f"{channel.mention} is now a LFG Channel with the {role.mention} role being mentioned.\n"
                f"To add more use the same command with the same channel selected, but a different role.",
                ephemeral=True
            )

        self.bot.settings.update_guilds()

    @discord.slash_command(description="Remove a LFG Channel.")
    @discord.default_permissions(administrator=True)
    async def setting_remove_lfg(self, ctx: ApplicationContext, channel: discord.TextChannel):
        if channel.id in ctx.g.lfg_channels:
            del ctx.g.lfg_channels[channel.id]
            self.bot.settings.update_settings()
            await ctx.respond(
                f"{channel.mention} is no longer a LFG Channel.",
                ephemeral=True
            )
        else:
            await ctx.respond(
                f"{channel.mention} is no LFG Channel!",
                ephemeral=True
            )


def setup(bot):
    bot.add_cog(SettingsCog(bot))
