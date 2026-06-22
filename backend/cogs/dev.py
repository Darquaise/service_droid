import asyncio
import io
import json
import logging
from pathlib import Path

import discord
from discord.ext import commands

from classes import ServiceDroid, LogView, TriviaHandler, TriviaQuestion
from classes.log_view import DEFAULT_LINES_PER_PAGE, LINES_PER_PAGE_OPTIONS
from classes.settings import env_int_list
from logging_setup import log_file_path

REPO_PATH = str(Path(__file__).resolve().parent.parent)
LOG_PATH = log_file_path()
DEBUG_GUILD_IDS = env_int_list("DEBUG_GUILD_IDS")

logger = logging.getLogger(__name__)

KEY_PERMS: list[tuple[str, str]] = [
    ("administrator", "Administrator"),
    ("manage_guild", "Manage Server"),
    ("manage_roles", "Manage Roles"),
    ("manage_channels", "Manage Channels"),
    ("manage_messages", "Manage Messages"),
    ("kick_members", "Kick"),
    ("ban_members", "Ban"),
    ("moderate_members", "Timeout"),
    ("manage_webhooks", "Manage Webhooks"),
    ("mention_everyone", "Mention Everyone"),
    ("view_audit_log", "Audit Log"),
    ("send_messages", "Send Messages"),
    ("embed_links", "Embed Links"),
    ("attach_files", "Attach Files"),
    ("read_message_history", "Read History"),
]

MAX_FIELD_VALUE = 1000
MAX_TOTAL_ROLE_CHARS = 4500


def _categorize_role(role: discord.Role) -> str:
    p = role.permissions
    if p.administrator:
        return "Admin"
    if p.manage_guild or p.manage_roles or p.manage_channels:
        return "Manager"
    if p.ban_members or p.kick_members:
        return "Moderator"
    if p.moderate_members or p.manage_messages:
        return "Mod-Lite"
    if p.mention_everyone:
        return "Herald"
    if p.view_audit_log:
        return "Watcher"
    return "Member"


def _build_guild_embed(guild: discord.Guild) -> discord.Embed:
    me = guild.me
    perms = me.guild_permissions

    granted = [label for attr, label in KEY_PERMS if getattr(perms, attr, False)]
    missing = [label for attr, label in KEY_PERMS if not getattr(perms, attr, False)]

    desc_lines = [
        f"**Members:** {guild.member_count if guild.member_count is not None else '?'}",
        f"**Owner:** `{guild.owner_id}`",
        "",
        "**Bot Permissions**",
        f"✅ {', '.join(granted) if granted else '—'}",
        f"❌ {', '.join(missing) if missing else '—'}",
    ]

    embed = discord.Embed(
        title=guild.name,
        description="\n".join(desc_lines),
        colour=discord.Colour.blurple(),
    )
    embed.set_footer(text=f"ID: {guild.id}")
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    bot_role_ids = {r.id for r in me.roles}
    # Skip @everyone; list top-first like Discord's sidebar.
    roles_sorted = sorted(
        (r for r in guild.roles if not r.is_default()),
        key=lambda r: r.position,
        reverse=True,
    )

    role_lines: list[str] = []
    for role in roles_sorted:
        marker = "🤖" if role.id in bot_role_ids else "▫️"
        name = role.name.replace("`", "ˋ")
        role_lines.append(f"{marker} `{name}` — {_categorize_role(role)}")

    field_values: list[str] = []
    current: list[str] = []
    current_len = 0
    total_used = 0
    truncated = 0

    for i, line in enumerate(role_lines):
        line_len = len(line) + 1
        if total_used + current_len + line_len > MAX_TOTAL_ROLE_CHARS:
            truncated = len(role_lines) - i
            break
        if current_len + line_len > MAX_FIELD_VALUE:
            field_values.append("\n".join(current))
            total_used += current_len
            current = [line]
            current_len = line_len
        else:
            current.append(line)
            current_len += line_len
    if current:
        field_values.append("\n".join(current))

    for i, value in enumerate(field_values):
        name = f"Roles ({len(roles_sorted)})" if i == 0 else "… cont."
        embed.add_field(name=name, value=value, inline=False)

    if not field_values:
        embed.add_field(name="Roles", value="*(none beyond @everyone)*", inline=False)
    elif truncated:
        embed.add_field(
            name="…",
            value=f"*+ {truncated} more roles truncated*",
            inline=False,
        )

    return embed


async def _guild_autocomplete(ctx: discord.AutocompleteContext) -> list[discord.OptionChoice]:
    bot = ctx.interaction.client
    query = (ctx.value or "").lower()
    results: list[discord.OptionChoice] = []
    for g in bot.guilds:
        if not query or query in g.name.lower() or query in str(g.id):
            label = f"{g.name} ({g.id})"[:100]
            results.append(discord.OptionChoice(name=label, value=str(g.id)))
        if len(results) >= 25:
            break
    return results


async def shutdown(bot: ServiceDroid):
    activity = discord.Activity(name='shutting down...', type=discord.ActivityType.playing)
    await bot.change_presence(activity=activity)
    await bot.close()


async def restart(bot: ServiceDroid):
    activity = discord.Activity(name='restarting...', type=discord.ActivityType.playing)
    await bot.change_presence(activity=activity)
    bot.exit_code = 42
    await bot.close()


class DevelopmentCog(commands.Cog):

    def __init__(self, bot: ServiceDroid):
        self.bot = bot
        logger.debug("dev cog loaded")

    @discord.slash_command(debug_guilds=DEBUG_GUILD_IDS)
    @discord.default_permissions(administrator=True)
    async def update_git(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)

        proc = await asyncio.create_subprocess_shell(
            "git pull",
            cwd=REPO_PATH,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        code = proc.returncode

        if code == 0:
            msg = stdout.decode().strip() or "No output"
            text = f"git pull successful:\n```{msg}```"
        else:
            out = (stdout.decode() + "\n" + stderr.decode()).strip()
            text = f"git pull failed (code {code}):\n```{out[:1800]}```"

        await ctx.followup.send(text, ephemeral=True)

    @commands.slash_command(description="Shuts down the Bot", debug_guilds=DEBUG_GUILD_IDS)
    @discord.default_permissions(administrator=True)
    async def shutdown(self, ctx: discord.ApplicationContext):
        await ctx.respond("Bot is shutting down", ephemeral=True)
        await shutdown(self.bot)

    @commands.slash_command(description="Restarts the Bot", debug_guilds=DEBUG_GUILD_IDS)
    @discord.default_permissions(administrator=True)
    async def restart(self, ctx: discord.ApplicationContext):
        await ctx.respond("Bot is restarting", ephemeral=True)
        await restart(self.bot)

    @commands.slash_command(description="Check if Bot responds", debug_guilds=DEBUG_GUILD_IDS)
    @discord.default_permissions(administrator=True)
    async def status(self, ctx: discord.ApplicationContext):
        await ctx.respond("Bot is here!", ephemeral=True)

    @discord.slash_command(description="Show the bot's terminal log", debug_guilds=DEBUG_GUILD_IDS)
    @discord.default_permissions(administrator=True)
    async def log(
            self,
            ctx: discord.ApplicationContext,
            lines_per_page: discord.Option(
                int,
                "Lines per page",
                required=False,
                default=DEFAULT_LINES_PER_PAGE,
                choices=LINES_PER_PAGE_OPTIONS,
            ) = DEFAULT_LINES_PER_PAGE,
    ):
        await ctx.defer(ephemeral=True)
        view = LogView(ctx, LOG_PATH, lines_per_page=lines_per_page)
        await ctx.followup.send(embed=view.build_embed(), view=view, ephemeral=True)

    @discord.slash_command(
        description="List all guilds with bot permissions and roles.",
        debug_guilds=DEBUG_GUILD_IDS,
    )
    @discord.default_permissions(administrator=True)
    async def list_guilds(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)

        guilds = sorted(self.bot.guilds, key=lambda g: g.name.lower())

        await ctx.followup.send(
            f"Bot is in **{len(guilds)}** guild{'s' if len(guilds) != 1 else ''}.",
            ephemeral=True,
        )

        for guild in guilds:
            embed = _build_guild_embed(guild)
            await ctx.followup.send(embed=embed, ephemeral=True)

    @discord.slash_command(
        description="Export the live guilds data as JSON.",
        debug_guilds=DEBUG_GUILD_IDS,
    )
    @discord.default_permissions(administrator=True)
    async def export_guilds(self, ctx: discord.ApplicationContext):
        await ctx.defer(ephemeral=True)

        guilds_data = self.bot.settings.get_live_guilds_dict()

        await ctx.followup.send(
            "Guilds export.",
            file=discord.File(
                io.BytesIO(json.dumps(guilds_data, indent=2, default=str).encode("utf-8")),
                filename="guilds.json",
            ),
            ephemeral=True,
        )

    @discord.slash_command(
        description="Export a guild's trivia questions as JSON.",
        debug_guilds=DEBUG_GUILD_IDS,
    )
    @discord.default_permissions(administrator=True)
    async def export_trivia(
            self,
            ctx: discord.ApplicationContext,
            guild_id: discord.Option(
                str, "Server", autocomplete=_guild_autocomplete,
            ),
    ):
        await ctx.defer(ephemeral=True)

        try:
            gid = int(guild_id)
        except ValueError:
            return await ctx.followup.send("Invalid guild ID.", ephemeral=True)

        guild = self.bot.get_guild(gid)
        if guild is None:
            return await ctx.followup.send(
                f"Bot is not in guild `{gid}`.", ephemeral=True,
            )

        trivia_data = self.bot.settings.get_live_trivia_dict(gid)
        if not trivia_data:
            return await ctx.followup.send(
                f"**{guild.name}** has no trivia data yet.", ephemeral=True,
            )

        buf = io.BytesIO(json.dumps(trivia_data, indent=2).encode("utf-8"))
        return await ctx.followup.send(
            f"Trivia export for **{guild.name}** (`{gid}`).",
            file=discord.File(buf, filename=f"trivia_{gid}.json"),
            ephemeral=True,
        )

    @discord.slash_command(
        description="Inject a trivia JSON into a chosen guild.",
        debug_guilds=DEBUG_GUILD_IDS,
    )
    @discord.default_permissions(administrator=True)
    async def inject_trivia(
            self,
            ctx: discord.ApplicationContext,
            guild_id: discord.Option(
                str, "Target server", autocomplete=_guild_autocomplete,
            ),
            attachment: discord.Option(
                discord.Attachment,
                "JSON file: {list_name: [{id, title, question, answer, answer_context}, ...]}",
            ),
            mode: discord.Option(
                str,
                "replace = overwrite all lists, merge = overwrite list-by-list",
                choices=["replace", "merge"],
                default="replace",
            ) = "replace",
    ):
        await ctx.defer(ephemeral=True)

        guild_id = int(guild_id)
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return await ctx.followup.send(f"Bot is not in guild `{guild_id}`.", ephemeral=True)

        if not attachment.filename.lower().endswith(".json"):
            return await ctx.followup.send("Attachment must be a `.json` file.", ephemeral=True)

        try:
            raw = await attachment.read()
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            return await ctx.followup.send(f"Invalid JSON: `{e}`", ephemeral=True)

        if not isinstance(data, dict):
            return await ctx.followup.send(
                "Top-level JSON must be an object mapping list names to question arrays.", ephemeral=True
            )

        new_lists: dict[str, list[TriviaQuestion]] = {}
        for list_name, questions in data.items():
            if not isinstance(list_name, str) or not isinstance(questions, list):
                return await ctx.followup.send(
                    f"Invalid entry `{list_name}`: must be a list of question objects.", ephemeral=True
                )
            try:
                new_lists[list_name] = [TriviaQuestion.from_json(q) for q in questions]
            except (KeyError, TypeError, ValueError) as e:
                return await ctx.followup.send(
                    f"Invalid question in list **{list_name}**: `{e}`", ephemeral=True
                )

        handler = TriviaHandler.get_or_create(guild)
        if mode == "replace":
            handler.lists = new_lists
        else:
            for name, qs in new_lists.items():
                handler.lists[name] = qs

        self.bot.settings.update_trivia(guild_id)

        counts = ", ".join(f"**{n}** ({len(q)})" for n, q in new_lists.items()) or "—"
        return await ctx.followup.send(
            f"Trivia for **{guild.name}** (`{guild_id}`) {mode}d.\n"
            f"Lists in payload: {counts}",
            ephemeral=True,
        )
