import discord

from classes.bot import ServiceDroid

time_units = ["days", "hours", "minutes", "seconds"]


class SettingsCog(discord.Cog):
    def __init__(self, bot: ServiceDroid):
        self.bot = bot

    @discord.slash_command(name="turn_lfg_on_or_off", description="Turn Looking for game requests on or off")
    @discord.default_permissions(administrator=True)
    async def turn_lfg(self, ctx: discord.ApplicationContext):
        self.bot.settings.active = not self.bot.settings.active
        self.bot.settings.update_settings()
        await ctx.respond(f"Looking for game command has be turned {'on' if self.bot.settings.active else 'off'}")

    @discord.slash_command(description="Change the amount of cooldown after a looking for game request")
    @discord.default_permissions(administrator=True)
    async def setting_cooldown(
            self,
            ctx: discord.ApplicationContext,
            time_unit: discord.Option(description="Of what kind the given time will be", choices=time_units),
            time_amount: discord.Option(name="amount", description="The amount of time", input_type=int)
    ):
        old_time = self.bot.settings.cooldown
        new_time = self.bot.settings.transform_time(time_amount, time_unit)

        if new_time == old_time:
            await ctx.respond(
                f"The cooldown has been set to {time_amount} {time_unit}. Nothing changed.",
                ephemeral=True
            )
        else:
            self.bot.settings.cooldown = new_time
            self.bot.settings.update_settings()
            await ctx.respond(
                f"The cooldown has been set to {time_amount} {time_unit}.",
                ephemeral=True
            )

    @discord.slash_command(
        description="Add roles to a channel for lfg. If the channel wasn't a lfg channel before it will be made one."
    )
    @discord.default_permissions(administrator=True)
    async def setting_add_lfg(
            self,
            ctx: discord.ApplicationContext,
            channel: discord.TextChannel,
            role: discord.Role
    ):
        allowed_channels = self.bot.settings.allowed_channels
        if channel.id in allowed_channels.keys():
            if role.id in allowed_channels[channel.id]:
                await ctx.respond(
                    f"{role.mention} is already being pinged on lfg in {channel.mention}",
                    ephemeral=True
                )
                return

            allowed_channels[channel.id].append(role.id)
            await ctx.respond(
                f"{role.mention} has been added to {channel.mention}\n"
                "Roles now being pinged in this channel: "
                f"{' '.join([ctx.guild.get_role(x).mention for x in allowed_channels[channel.id]])}",
                ephemeral=True
            )
        else:
            allowed_channels[channel.id] = [role.id]
            await ctx.respond(
                f"{channel.mention} is now a lfg channel with the {role.mention} role being pinged.",
                ephemeral=True
            )
        self.bot.settings.update_settings()

    @discord.slash_command(description="Remove lfg channels.")
    @discord.default_permissions(administrator=True)
    async def setting_remove_lfg(self, ctx: discord.ApplicationContext, channel: discord.TextChannel):
        if channel.id in self.bot.settings.allowed_channels.keys():
            del self.bot.settings.allowed_channels[channel.id]
            self.bot.settings.update_settings()
            await ctx.respond(
                f"{channel.mention} no longer is a lfg channel!",
                ephemeral=True
            )
        else:
            await ctx.respond(
                f"{channel.mention} is no lfg channel.",
                ephemeral=True
            )
