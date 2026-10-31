"""Everything that couples the e2e harness to py-cord internals lives in this module.

Commands and components are triggered with synthetic ``INTERACTION_CREATE`` payloads that go through
``ConnectionState.parse_interaction_create`` (state.py), so command resolution, option conversion,
checks, the callback and the error handlers run for real. Only the HTTP calls that answer such an
interaction are intercepted: py-cord sends all of them through ``AsyncWebhookAdapter.request``
(webhook/async_.py), not through ``HTTPClient``:

- ``POST /interactions/{id}/{token}/callback``       first response, defer, update, modal
- ``POST /webhooks/{app}/{token}``                    followup messages
- ``GET|PATCH|DELETE /webhooks/{app}/{token}/messages/@original`` and ``.../messages/{id}``

Synthetic interactions carry a token starting with ``TOKEN_PREFIX``; every other request (including
webhooks that are not ours) is passed through to Discord untouched.

Also here: the bot's local permission view is demoted from Administrator so channel overwrites count
(``demote_bot_admin``).
"""

from __future__ import annotations

import asyncio
import io
import itertools
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Iterable

import discord
from discord.ui.view import BaseView, ViewStore
from discord.webhook.async_ import AsyncWebhookAdapter

logger = logging.getLogger(__name__)

TOKEN_PREFIX = "e2e."
DISCORD_EPOCH = 1420070400000
EPHEMERAL = 1 << 6

# InteractionResponseType
RESP_CHANNEL_MESSAGE = 4
RESP_DEFERRED_CHANNEL_MESSAGE = 5
RESP_DEFERRED_UPDATE = 6
RESP_UPDATE_MESSAGE = 7
RESP_MODAL = 9

# what Discord enforces on an answer; the synthetic path must reject what the real one would
INITIAL_RESPONSE_DEADLINE = 3.0
MAX_CONTENT = 2000
MAX_EMBEDS = 10
MAX_EMBED_TOTAL = 6000
EMBED_FIELD_LIMITS = {"title": 256, "description": 4096}
MAX_FIELDS = 25
MAX_FIELD_NAME = 256
MAX_FIELD_VALUE = 1024
MAX_FOOTER = 2048
MAX_AUTHOR = 256
MAX_ACTION_ROWS = 5
MAX_ROW_ITEMS = 5
MAX_LABEL = 80
MAX_CUSTOM_ID = 100
MAX_SELECT_OPTIONS = 25

# SlashCommandOptionType
OPT_SUB_COMMAND = 1
OPT_SUB_COMMAND_GROUP = 2

MirrorHook = Callable[["CapturedMessage", str], Awaitable[None]]


class HarnessError(Exception):
    """Misuse of the harness or a state the synthetic interaction cannot reach."""


class CommandNotAvailable(HarnessError):
    """Discord would not let this member run the command (default_member_permissions)."""


class CommandFailed(HarnessError):
    """The command or component callback raised."""

    def __init__(self, response: "Response", errors: list[BaseException]):
        self.response = response
        self.errors = errors
        super().__init__(
            f"/{response.command} raised {errors[0]!r}" + (f" (+{len(errors) - 1} more)" if len(errors) > 1 else "")
        )


class InteractionTimeout(HarnessError):
    """The interaction did not settle in time."""


# ---------------------------------------------------------------------------------------------
# ids
# ---------------------------------------------------------------------------------------------

_counter = itertools.count(1)
_last_ms = 0


def new_snowflake() -> int:
    global _last_ms
    ms = max(int(time.time() * 1000) - DISCORD_EPOCH, _last_ms)
    _last_ms = ms
    return (ms << 22) | (next(_counter) & 0x3FFFFF)


def _iso(dt: datetime | None = None) -> str:
    return (dt or datetime.now(timezone.utc)).isoformat()


# ---------------------------------------------------------------------------------------------
# captured responses
# ---------------------------------------------------------------------------------------------

@dataclass(slots=True)
class CapturedFile:
    filename: str
    data: bytes


@dataclass(slots=True)
class CapturedComponent:
    kind: str  # "button" | "select"
    custom_id: str | None
    label: str | None
    disabled: bool
    style: int | None = None
    url: str | None = None
    options: list[str] = field(default_factory=list)


def _flatten_components(rows: Iterable[dict]) -> list[CapturedComponent]:
    found: list[CapturedComponent] = []

    def walk(node: dict) -> None:
        kind = node.get("type")
        if kind == 2:
            found.append(CapturedComponent(
                "button", node.get("custom_id"), node.get("label"), bool(node.get("disabled")),
                node.get("style"), node.get("url"),
            ))
        elif kind == 3:
            found.append(CapturedComponent(
                "select", node.get("custom_id"), node.get("placeholder"), bool(node.get("disabled")),
                options=[o["value"] for o in node.get("options", [])],
            ))
        for child in node.get("components", []):
            walk(child)

    for row in rows:
        walk(row)
    return found


@dataclass(slots=True)
class CapturedMessage:
    """One message the bot produced as an answer to an interaction (state after all edits)."""

    id: int
    channel_id: int
    kind: str  # "original" | "followup"
    interaction: "Response"
    content: str = ""
    embeds: list[discord.Embed] = field(default_factory=list)
    files: list[CapturedFile] = field(default_factory=list)
    components: list[CapturedComponent] = field(default_factory=list)
    flags: int = 0
    allowed_mentions: dict | None = None
    loading: bool = False
    deleted: bool = False
    edits: int = 0
    mirror: discord.Message | None = None
    _attachments: list[dict] = field(default_factory=list)
    _raw_components: list[dict] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    edited_at: datetime | None = None

    @property
    def ephemeral(self) -> bool:
        return bool(self.flags & EPHEMERAL)

    @property
    def text(self) -> str:
        """Content plus everything readable in the embeds, for substring assertions."""
        parts = [self.content]
        for embed in self.embeds:
            parts += [embed.title or "", embed.description or ""]
            parts += [f"{f.name}\n{f.value}" for f in embed.fields]
            if embed.footer and embed.footer.text:
                parts.append(embed.footer.text)
        return "\n".join(p for p in parts if p)

    @property
    def filenames(self) -> list[str]:
        return [f.filename for f in self.files]

    def component(self, target: str) -> CapturedComponent:
        """Find a component by custom_id first, then by label."""
        for c in self.components:
            if c.custom_id == target:
                return c
        matches = [c for c in self.components if c.label == target]
        if len(matches) == 1:
            return matches[0]
        known = [(c.custom_id, c.label) for c in self.components]
        raise HarnessError(f"no unique component {target!r} on message {self.id}; has {known}")

    def apply(self, data: dict, uploaded: list[CapturedFile]) -> None:
        if "content" in data:
            self.content = data["content"] or ""
        if "embeds" in data:
            self.embeds = [discord.Embed.from_dict(e) for e in data["embeds"]]
        if "components" in data:
            self._raw_components = data["components"]
            self.components = _flatten_components(data["components"])
        if "flags" in data:
            # the ephemeral bit is fixed at creation, an edit can't flip it
            self.flags = (self.flags & EPHEMERAL) | (data["flags"] & ~EPHEMERAL)
        if "allowed_mentions" in data:
            self.allowed_mentions = data["allowed_mentions"]
        if "attachments" in data:
            kept_ids = {int(a["id"]) for a in data["attachments"]}
            kept = [a for a in self._attachments if int(a["id"]) in kept_ids]
            self.files = [f for f, a in zip(self.files, self._attachments) if a in kept]
            self._attachments = kept
        for f in uploaded:
            self._attachments.append({"id": str(new_snowflake()), "filename": f.filename})
            self.files.append(f)
        self.loading = False

    def payload(self, application_id: int, author: dict) -> dict:
        return {
            "id": str(self.id),
            "channel_id": str(self.channel_id),
            "author": author,
            "content": self.content,
            "timestamp": _iso(self.created_at),
            "edited_timestamp": _iso(self.edited_at) if self.edited_at else None,
            "tts": False,
            "mention_everyone": False,
            "mentions": [],
            "mention_roles": [],
            "attachments": [
                {
                    "id": a["id"], "filename": a["filename"], "size": len(f.data),
                    "url": f"https://e2e.invalid/{a['id']}/{a['filename']}",
                    "proxy_url": f"https://e2e.invalid/{a['id']}/{a['filename']}",
                }
                for a, f in zip(self._attachments, self.files)
            ],
            "embeds": [e.to_dict() for e in self.embeds],
            "pinned": False,
            "type": 20,
            "flags": self.flags,
            "components": self._raw_components,
            "webhook_id": str(application_id),
            "application_id": str(application_id),
        }

    def __repr__(self) -> str:
        return (
            f"<CapturedMessage {self.kind} id={self.id} ephemeral={self.ephemeral} "
            f"content={self.content[:40]!r} embeds={len(self.embeds)} files={self.filenames}>"
        )


class Response:
    """Everything the bot answered to one synthetic interaction."""

    def __init__(
            self, interaction_id: int, token: str, command: str, user: discord.Member,
            channel: discord.abc.GuildChannel, kind: str,
    ):
        self.interaction_id = interaction_id
        self.token = token
        self.command = command
        self.user = user
        self.channel = channel
        self.kind = kind  # "command" | "component"
        self.messages: list[CapturedMessage] = []
        self.errors: list[BaseException] = []
        self.callback_type: int | None = None
        self.source: CapturedMessage | None = None  # component interactions: the message clicked on
        self.modal: dict | None = None
        self._pending = 0
        self._started = False

    @property
    def original(self) -> CapturedMessage | None:
        return next((m for m in self.messages if m.kind == "original"), None)

    first = original

    @property
    def followups(self) -> list[CapturedMessage]:
        return [m for m in self.messages if m.kind == "followup"]

    @property
    def last(self) -> CapturedMessage | None:
        live = [m for m in self.messages if not m.deleted]
        return live[-1] if live else None

    @property
    def view_message(self) -> CapturedMessage | None:
        """The message that carries components: the last one that has any, else the original."""
        for m in reversed(self.messages):
            if m.components and not m.deleted:
                return m
        return self.source if self.source is not None and self.source.components else self.original

    @property
    def ephemeral(self) -> bool:
        first = self.original
        return bool(first and first.ephemeral)

    @property
    def text(self) -> str:
        """All readable text of every message this interaction touched (answers and the edited source)."""
        messages = list(self.messages)
        if self.source is not None and self.source not in messages:
            messages.append(self.source)
        return "\n".join(m.text for m in messages if not m.deleted)

    def __iter__(self):
        return iter(self.messages)

    def __getitem__(self, index: int) -> CapturedMessage:
        return self.messages[index]

    def __repr__(self) -> str:
        return f"<Response /{self.command} by {self.user} messages={self.messages}>"


# ---------------------------------------------------------------------------------------------
# payload builders
# ---------------------------------------------------------------------------------------------

def user_payload(user: discord.abc.User) -> dict:
    return {
        "id": str(user.id),
        "username": user.name,
        "discriminator": getattr(user, "discriminator", "0"),
        "global_name": getattr(user, "global_name", None),
        "avatar": getattr(user, "_avatar", None),
        "bot": user.bot,
        "system": getattr(user, "system", False),
        "public_flags": 0,
    }


def member_payload(member: discord.Member, channel: discord.abc.GuildChannel | None = None) -> dict:
    permissions = channel.permissions_for(member) if channel is not None else member.guild_permissions
    return {
        "user": user_payload(member),
        "roles": [str(r.id) for r in member.roles if not r.is_default()],
        "nick": member.nick,
        "joined_at": _iso(member.joined_at),
        "premium_since": None,
        "deaf": False,
        "mute": False,
        "flags": 0,
        "pending": False,
        "communication_disabled_until": None,
        "permissions": str(permissions.value),
    }


def role_payload(role: discord.Role) -> dict:
    return {
        "id": str(role.id),
        "name": role.name,
        "color": role.colors.primary.value,
        "colors": {"primary_color": role.colors.primary.value, "secondary_color": None, "tertiary_color": None},
        "hoist": role.hoist,
        "position": role.position,
        "permissions": str(role.permissions.value),
        "managed": role.managed,
        "mentionable": role.mentionable,
        "icon": None,
        "unicode_emoji": None,
        "flags": 0,
    }


def channel_payload(channel: discord.abc.GuildChannel, member: discord.Member | None = None) -> dict:
    return {
        "id": str(channel.id),
        "type": channel.type.value,
        "name": channel.name,
        "parent_id": str(channel.category_id) if channel.category_id else None,
        "permissions": str(channel.permissions_for(member).value) if member else "0",
        "flags": 0,
    }


def _resolve_command(bot: discord.Bot, guild: discord.Guild, path: tuple[str, ...]):
    """Find the (sub)command for ``path``; returns ``(leaf, [top, *chain])``."""
    candidates = [
        c for c in bot.application_commands
        if c.name == path[0] and isinstance(c, (discord.SlashCommand, discord.SlashCommandGroup))
    ]
    scoped = [c for c in candidates if not c.guild_ids or guild.id in c.guild_ids]
    if not scoped:
        raise HarnessError(f"slash command {path[0]!r} is not registered for this guild")
    top = scoped[0]
    chain = [top]
    node = top
    for name in path[1:]:
        subs = getattr(node, "subcommands", None)
        if subs is None:
            raise HarnessError(f"/{' '.join(path)}: {node.name!r} has no subcommands")
        node = next((s for s in subs if s.name == name), None)
        if node is None:
            raise HarnessError(f"/{' '.join(path)}: no subcommand {name!r}")
        chain.append(node)
    if isinstance(node, discord.SlashCommandGroup):
        raise HarnessError(f"/{' '.join(path)} is a group; give a subcommand")
    return node, chain


def _option_value(option: discord.Option, value: Any, resolved: dict) -> Any:
    """Convert a Python value to the wire value for ``option``; fills ``resolved`` for snowflakes."""
    t = option.input_type
    T = discord.SlashCommandOptionType
    if t == T.user or t == T.mentionable and isinstance(value, discord.abc.User):
        if isinstance(value, int):
            raise HarnessError(f"option {option.name!r}: pass a Member, not an id")
        resolved.setdefault("users", {})[str(value.id)] = user_payload(value)
        if isinstance(value, discord.Member):
            resolved.setdefault("members", {})[str(value.id)] = {
                k: v for k, v in member_payload(value).items() if k != "user"
            }
        return str(value.id)
    if t == T.role or t == T.mentionable and isinstance(value, discord.Role):
        resolved.setdefault("roles", {})[str(value.id)] = role_payload(value)
        return str(value.id)
    if t == T.channel:
        resolved.setdefault("channels", {})[str(value.id)] = channel_payload(value)
        return str(value.id)
    if t == T.integer:
        return int(value)
    if t == T.number:
        return float(value)
    if t == T.boolean:
        return bool(value)
    if t == T.string:
        return str(value)
    raise HarnessError(f"option {option.name!r}: type {t.name} is not supported by the harness")


def build_options(command: discord.SlashCommand, given: dict[str, Any], resolved: dict) -> list[dict]:
    by_name = {o.name: o for o in command.options}
    unknown = set(given) - set(by_name)
    if unknown:
        raise HarnessError(f"/{command.qualified_name}: unknown option(s) {sorted(unknown)}; has {sorted(by_name)}")
    out = []
    for name, option in by_name.items():
        if name not in given:
            if option.required:
                raise HarnessError(f"/{command.qualified_name}: missing required option {name!r}")
            continue
        value = given[name]
        if option.choices and not any(c.value == value for c in option.choices):
            raise HarnessError(
                f"/{command.qualified_name}: {name}={value!r} is not one of {[c.value for c in option.choices]}"
            )
        out.append({"name": name, "type": option.input_type.value, "value": _option_value(option, value, resolved)})
    return out


def _base_interaction(
        bot: discord.Client, token: str, kind: int, guild: discord.Guild,
        channel: discord.abc.GuildChannel, member: discord.Member,
) -> dict:
    return {
        "id": str(new_snowflake()),
        "application_id": str(bot.user.id),
        "type": kind,
        "token": token,
        "version": 1,
        "guild_id": str(guild.id),
        "channel_id": str(channel.id),
        "channel": channel_payload(channel, member),
        "member": member_payload(member, channel),
        "locale": "en-US",
        "guild_locale": "en-US",
        "app_permissions": str(channel.permissions_for(guild.me).value),
        "context": 0,
        "authorizing_integration_owners": {"0": str(guild.id)},
        "entitlements": [],
        "attachment_size_limit": 8388608,
    }


def build_command_payload(
        bot: discord.Client, token: str, guild: discord.Guild, channel: discord.abc.GuildChannel,
        member: discord.Member, path: tuple[str, ...], options: dict[str, Any],
) -> tuple[dict, discord.SlashCommand, list]:
    leaf, chain = _resolve_command(bot, guild, path)
    resolved: dict = {}
    wire = build_options(leaf, options, resolved)
    for name in reversed(path[1:]):
        node_type = OPT_SUB_COMMAND if name == path[-1] else OPT_SUB_COMMAND_GROUP
        wire = [{"name": name, "type": node_type, "options": wire}]
    data = {
        "id": str(chain[0].id) if chain[0].id else str(new_snowflake()),
        "name": path[0],
        "type": 1,
        "guild_id": str(guild.id),
        "options": wire,
    }
    if resolved:
        data["resolved"] = resolved
    payload = _base_interaction(bot, token, 2, guild, channel, member)
    payload["data"] = data
    return payload, leaf, chain


def build_component_payload(
        bot: discord.Client, token: str, guild: discord.Guild, channel: discord.abc.GuildChannel,
        member: discord.Member, message: CapturedMessage, component: CapturedComponent,
        values: list[str] | None,
) -> dict:
    payload = _base_interaction(bot, token, 3, guild, channel, member)
    data: dict[str, Any] = {
        "custom_id": component.custom_id,
        "component_type": 2 if component.kind == "button" else 3,
    }
    if component.kind == "select":
        data["values"] = list(values or [])
    payload["data"] = data
    payload["message"] = message.payload(bot.user.id, user_payload(bot.user))
    return payload


def validate_message(data: dict) -> list[str]:
    """Everything in a message body that Discord would answer with 400 Invalid Form Body."""
    problems = []
    content = data.get("content") or ""
    if len(content) > MAX_CONTENT:
        problems.append(f"content has {len(content)} characters (max {MAX_CONTENT})")
    embeds = data.get("embeds") or []
    if len(embeds) > MAX_EMBEDS:
        problems.append(f"{len(embeds)} embeds (max {MAX_EMBEDS})")
    total = 0
    for i, embed in enumerate(embeds):
        for key, limit in EMBED_FIELD_LIMITS.items():
            value = embed.get(key) or ""
            total += len(value)
            if len(value) > limit:
                problems.append(f"embed {i} {key} has {len(value)} characters (max {limit})")
        fields = embed.get("fields") or []
        if len(fields) > MAX_FIELDS:
            problems.append(f"embed {i} has {len(fields)} fields (max {MAX_FIELDS})")
        for f in fields:
            name, value = f.get("name") or "", f.get("value") or ""
            total += len(name) + len(value)
            if len(name) > MAX_FIELD_NAME:
                problems.append(f"embed {i} field name has {len(name)} characters (max {MAX_FIELD_NAME})")
            if len(value) > MAX_FIELD_VALUE:
                problems.append(f"embed {i} field {name!r} has {len(value)} characters (max {MAX_FIELD_VALUE})")
        footer = (embed.get("footer") or {}).get("text") or ""
        author = (embed.get("author") or {}).get("name") or ""
        total += len(footer) + len(author)
        if len(footer) > MAX_FOOTER:
            problems.append(f"embed {i} footer has {len(footer)} characters (max {MAX_FOOTER})")
        if len(author) > MAX_AUTHOR:
            problems.append(f"embed {i} author has {len(author)} characters (max {MAX_AUTHOR})")
    if total > MAX_EMBED_TOTAL:
        problems.append(f"embeds have {total} characters in total (max {MAX_EMBED_TOTAL})")
    rows = data.get("components") or []
    if len(rows) > MAX_ACTION_ROWS:
        problems.append(f"{len(rows)} action rows (max {MAX_ACTION_ROWS})")
    for row in rows:
        items = row.get("components") or []
        if row.get("type") == 1 and len(items) > MAX_ROW_ITEMS:
            problems.append(f"an action row has {len(items)} items (max {MAX_ROW_ITEMS})")
        for item in items:
            label = item.get("label") or ""
            custom_id = item.get("custom_id") or ""
            if len(label) > MAX_LABEL:
                problems.append(f"component label {label[:20]!r}… has {len(label)} characters (max {MAX_LABEL})")
            if len(custom_id) > MAX_CUSTOM_ID:
                problems.append(f"custom_id has {len(custom_id)} characters (max {MAX_CUSTOM_ID})")
            if len(item.get("options") or []) > MAX_SELECT_OPTIONS:
                problems.append(f"select has {len(item['options'])} options (max {MAX_SELECT_OPTIONS})")
    return problems


def snowflake_time(snowflake: int) -> float:
    return ((snowflake >> 22) + DISCORD_EPOCH) / 1000


def required_permissions(chain: list) -> discord.Permissions | None:
    for node in reversed(chain):
        if node.default_member_permissions is not None:
            return node.default_member_permissions
    return None


# ---------------------------------------------------------------------------------------------
# the gateway: interception + dispatch
# ---------------------------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, status: int, reason: str):
        self.status = status
        self.reason = reason


class InteractionGateway:
    def __init__(self, bot: discord.Client, mirror: MirrorHook | None = None):
        self.bot = bot
        self.mirror = mirror
        self.by_token: dict[str, Response] = {}
        self.by_interaction_id: dict[int, Response] = {}
        self._originals: list[tuple[Any, str, Any]] = []
        self._installed = False

    # -- installation -----------------------------------------------------------------------

    def _patch(self, owner: Any, name: str, replacement: Any) -> None:
        if name not in owner.__dict__:
            raise HarnessError(
                f"py-cord {discord.__version__}: {owner.__name__}.{name} is gone — the e2e harness "
                f"(e2e/harness/pycord.py) has to be adapted to this py-cord version"
            )
        self._originals.append((owner, name, owner.__dict__[name]))
        setattr(owner, name, replacement)

    def install(self) -> None:
        if self._installed:
            return
        gateway = self

        if not hasattr(self.bot._connection, "parse_interaction_create"):
            raise HarnessError(
                f"py-cord {discord.__version__}: ConnectionState.parse_interaction_create is gone — "
                f"adapt e2e/harness/pycord.py"
            )
        original_request = AsyncWebhookAdapter.request

        async def request(adapter, route, session=None, **kwargs):
            token = route.webhook_token
            if isinstance(token, str) and token.startswith(TOKEN_PREFIX):
                return await gateway._handle(route, kwargs)
            return await original_request(adapter, route, session, **kwargs)

        self._patch(AsyncWebhookAdapter, "request", request)

        original_dispatch = ViewStore.dispatch

        def dispatch(store, component_type, custom_id, interaction):
            result = original_dispatch(store, component_type, custom_id, interaction)
            rec = gateway.by_interaction_id.get(interaction.id)
            if rec is not None and rec.kind == "component":
                rec._started = True
                # a stopped view returns early from _dispatch_item and never schedules the callback
                if interaction.view is not None and not interaction.view.is_finished():
                    rec._pending += 1
            return result

        self._patch(ViewStore, "dispatch", dispatch)

        original_task = BaseView._scheduled_task

        async def scheduled_task(view, item, interaction):
            rec = gateway.by_interaction_id.get(interaction.id)
            try:
                return await original_task(view, item, interaction)
            finally:
                if rec is not None:
                    rec._pending -= 1

        self._patch(BaseView, "_scheduled_task", scheduled_task)

        original_process = self.bot.process_application_commands

        async def process(interaction, *args, **kwargs):
            rec = gateway.by_interaction_id.get(interaction.id)
            try:
                return await original_process(interaction, *args, **kwargs)
            finally:
                if rec is not None and rec.kind == "command" and interaction.type is discord.InteractionType.application_command:
                    rec._pending -= 1

        self.bot.process_application_commands = process
        self._originals.append((self.bot, "process_application_commands", _MISSING))

        self.bot.add_listener(self._on_command_error, "on_application_command_error")
        self.bot.add_listener(self._on_view_error, "on_view_error")
        self._installed = True

    def uninstall(self) -> None:
        for owner, name, original in reversed(self._originals):
            if original is _MISSING:
                try:
                    delattr(owner, name)
                except AttributeError:
                    pass
            else:
                setattr(owner, name, original)
        self._originals.clear()
        self.bot.remove_listener(self._on_command_error, "on_application_command_error")
        self.bot.remove_listener(self._on_view_error, "on_view_error")
        self._installed = False

    async def _on_command_error(self, ctx, error) -> None:
        rec = self.by_interaction_id.get(ctx.interaction.id)
        if rec is not None:
            rec.errors.append(getattr(error, "original", error))

    async def _on_view_error(self, error, item, interaction) -> None:
        rec = self.by_interaction_id.get(interaction.id)
        if rec is not None:
            rec.errors.append(error)

    # -- dispatching ------------------------------------------------------------------------

    def _register(self, rec: Response, payload: dict) -> None:
        self.by_token[rec.token] = rec
        self.by_interaction_id[int(payload["id"])] = rec
        rec.interaction_id = int(payload["id"])

    async def run_command(
            self, *, guild: discord.Guild, channel: discord.abc.GuildChannel, member: discord.Member,
            path: tuple[str, ...], options: dict[str, Any], enforce_permissions: bool = True,
            expect_error: bool = False, timeout: float = 30.0,
    ) -> Response:
        token = f"{TOKEN_PREFIX}{next(_counter)}.{new_snowflake()}"
        payload, leaf, chain = build_command_payload(self.bot, token, guild, channel, member, path, options)

        needed = required_permissions(chain)
        if enforce_permissions and needed is not None:
            have = channel.permissions_for(member)
            if not have.administrator and not needed <= have:
                raise CommandNotAvailable(
                    f"{member} lacks {[n for n, v in needed if v and not getattr(have, n)]} for /{' '.join(path)}"
                )

        rec = Response(0, token, " ".join(path), member, channel, "command")
        rec._pending = 1
        rec._started = True
        self._register(rec, payload)
        self.bot._connection.parse_interaction_create(payload)
        return await self._settle(rec, timeout, expect_error)

    async def run_component(
            self, *, guild: discord.Guild, channel: discord.abc.GuildChannel, member: discord.Member,
            message: CapturedMessage, component: CapturedComponent, values: list[str] | None = None,
            expect_error: bool = False, timeout: float = 30.0,
    ) -> Response:
        if component.disabled:
            raise HarnessError(f"component {component.custom_id!r} is disabled; Discord would not send a click")
        token = f"{TOKEN_PREFIX}{next(_counter)}.{new_snowflake()}"
        payload = build_component_payload(self.bot, token, guild, channel, member, message, component, values)
        rec = Response(0, token, f"component:{component.label or component.custom_id}", member, channel, "component")
        rec.source = message
        self._register(rec, payload)
        self.bot._connection.parse_interaction_create(payload)
        if rec._pending == 0:
            raise HarnessError(
                f"no view is registered for {component.custom_id!r} on message {message.id}: "
                f"it timed out, was stopped, or its message was replaced"
            )
        return await self._settle(rec, timeout, expect_error)

    async def _settle(self, rec: Response, timeout: float, expect_error: bool) -> Response:
        deadline = time.monotonic() + timeout
        while not (rec._started and rec._pending <= 0):
            if time.monotonic() > deadline:
                raise InteractionTimeout(f"/{rec.command} did not finish within {timeout}s ({rec!r})")
            await asyncio.sleep(0.02)
        if rec.errors:
            # py-cord runs the error handlers as separate tasks; their answer belongs to this interaction
            await self._drain_error_handlers(deadline)
        if rec.errors and not expect_error:
            raise CommandFailed(rec, rec.errors)
        return rec

    @staticmethod
    async def _drain_error_handlers(deadline: float) -> None:
        names = {"pycord: on_application_command_error", "pycord: on_view_error"}
        current = asyncio.current_task()
        while True:
            pending = [
                t for t in asyncio.all_tasks()
                if t is not current and not t.done() and t.get_name() in names
            ]
            if not pending or time.monotonic() > deadline:
                return
            await asyncio.wait(pending, timeout=max(0.0, deadline - time.monotonic()))

    # -- the fake interaction API -----------------------------------------------------------

    async def _mirror(self, message: CapturedMessage, event: str) -> None:
        if self.mirror is None:
            return
        try:
            await self.mirror(message, event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("mirroring %s of %r failed", event, message)

    def _parse(self, kwargs: dict) -> tuple[dict, list[CapturedFile]]:
        data: dict = {}
        payload = kwargs.get("payload")
        multipart = kwargs.get("multipart")
        if payload is not None:
            data = payload
        elif multipart:
            for part in multipart:
                if part.get("name") == "payload_json":
                    data = json.loads(part["value"])
                    break
        uploaded: list[CapturedFile] = []
        for f in kwargs.get("files") or []:
            f.reset(seek=True)
            uploaded.append(CapturedFile(f.filename, f.fp.read()))
        return data, uploaded

    def _new_message(self, rec: Response, kind: str, flags: int) -> CapturedMessage:
        message = CapturedMessage(new_snowflake(), rec.channel.id, kind, rec, flags=flags)
        rec.messages.append(message)
        return message

    def _author(self) -> dict:
        return user_payload(self.bot.user)

    def _message_json(self, message: CapturedMessage) -> dict:
        return message.payload(self.bot.user.id, self._author())

    def _not_found(self, what: str, code: int = 10008) -> discord.NotFound:
        return discord.NotFound(_FakeResponse(404, "Not Found"), {"message": what, "code": code})

    def _check_body(self, rec: Response, data: dict) -> None:
        problems = validate_message(data)
        if problems:
            logger.warning("e2e: /%s sent an answer Discord would reject: %s", rec.command, problems)
            raise discord.HTTPException(
                _FakeResponse(400, "Bad Request"),
                {"message": "Invalid Form Body: " + "; ".join(problems), "code": 50035},
            )

    async def _handle(self, route, kwargs: dict) -> Any:
        rec = self.by_token.get(route.webhook_token)
        if rec is None:
            # an answer that arrives after the per-test reset
            logger.warning("e2e: %s %s for an interaction that is no longer tracked", route.method, route.path)
            raise self._not_found("Unknown Webhook", 10015)
        data, uploaded = self._parse(kwargs)
        path = route.path
        method = route.method

        if path.endswith("/callback"):
            return await self._callback(rec, data, uploaded)

        if method == "POST" and path == "/webhooks/{webhook_id}/{webhook_token}":
            return await self._followup(rec, data, uploaded)

        if "/messages/" in path:
            target = self._target(rec, route)
            if method == "GET":
                return self._message_json(target)
            if method == "PATCH":
                return await self._edit(rec, target, data, uploaded)
            if method == "DELETE":
                target.deleted = True
                await self._mirror(target, "delete")
                return None

        raise HarnessError(f"unhandled interaction request {method} {route.url}")

    def _target(self, rec: Response, route) -> CapturedMessage:
        ident = route.url.rsplit("/", 1)[-1]
        if ident == "@original":
            target = rec.original
            if target is None and rec.source is not None:
                target = rec.source
            if target is None:
                raise self._not_found("Unknown Webhook")
            return target
        for m in rec.messages:
            if str(m.id) == ident:
                return m
        raise self._not_found("Unknown Message")

    async def _callback(self, rec: Response, body: dict, uploaded: list[CapturedFile]) -> dict:
        kind = body["type"]
        data = body.get("data") or {}
        late = time.time() - snowflake_time(rec.interaction_id)
        if late > INITIAL_RESPONSE_DEADLINE:
            logger.warning("e2e: /%s answered after %.1fs, Discord would have dropped it", rec.command, late)
            raise self._not_found("Unknown interaction", 10062)
        if kind in (RESP_CHANNEL_MESSAGE, RESP_UPDATE_MESSAGE):
            self._check_body(rec, data)
        rec.callback_type = kind
        loading = kind in (RESP_DEFERRED_CHANNEL_MESSAGE, RESP_DEFERRED_UPDATE)
        interaction_info = {
            "id": str(rec.interaction_id),
            "type": 2 if rec.kind == "command" else 3,
            "response_message_loading": kind == RESP_DEFERRED_CHANNEL_MESSAGE,
            "response_message_ephemeral": bool(data.get("flags", 0) & EPHEMERAL),
        }
        resource: dict[str, Any] = {"type": kind}

        if kind == RESP_CHANNEL_MESSAGE:
            message = self._new_message(rec, "original", data.get("flags", 0))
            message.apply(data, uploaded)
            await self._mirror(message, "create")
            resource["message"] = self._message_json(message)
        elif kind == RESP_DEFERRED_CHANNEL_MESSAGE:
            message = self._new_message(rec, "original", data.get("flags", 0))
            message.loading = True
        elif kind == RESP_UPDATE_MESSAGE:
            target = rec.source
            if target is None:
                raise HarnessError("an update response needs a component interaction")
            await self._edit(rec, target, data, uploaded)
            resource["message"] = self._message_json(target)
        elif kind == RESP_MODAL:
            rec.modal = data
        elif not loading:
            raise HarnessError(f"unsupported interaction response type {kind}")
        return {"interaction": interaction_info, "resource": resource}

    async def _followup(self, rec: Response, data: dict, uploaded: list[CapturedFile]) -> dict:
        self._check_body(rec, data)
        original = rec.original
        if original is not None and original.loading:
            # the first followup after a defer turns the "thinking" message into the answer
            original.flags |= data.get("flags", 0) & ~EPHEMERAL
            original.apply(data, uploaded)
            await self._mirror(original, "create")
            return self._message_json(original)
        message = self._new_message(rec, "followup", data.get("flags", 0))
        message.apply(data, uploaded)
        await self._mirror(message, "create")
        return self._message_json(message)

    async def _edit(self, rec: Response, target: CapturedMessage, data: dict, uploaded: list[CapturedFile]) -> dict:
        self._check_body(rec, data)
        was_loading = target.loading
        target.apply(data, uploaded)
        if was_loading:
            await self._mirror(target, "create")
        else:
            target.edits += 1
            target.edited_at = datetime.now(timezone.utc)
            await self._mirror(target, "edit")
        return self._message_json(target)


_MISSING = object()


# ---------------------------------------------------------------------------------------------
# permissions
# ---------------------------------------------------------------------------------------------

def demote_bot_admin(guild: discord.Guild) -> None:
    """Make the bot's cached roles carry every permission except Administrator.

    The test bot is invited with Administrator, which makes ``permissions_for`` skip channel
    overwrites entirely. Without this the bot's own permission checks (Attach Files, Send Messages,
    ...) could never fail in the sandbox. Only the local cache changes; Discord still treats the bot
    as an administrator. A ``GUILD_ROLE_UPDATE`` for the bot's role undoes it, so the session fixture
    calls this again on every such event.
    """
    everything = discord.Permissions.all()
    everything.administrator = False
    for role in guild.me.roles:
        if role.is_default():
            continue
        role._permissions = everything.value


def bot_bytes(files: list[CapturedFile]) -> list[discord.File]:
    return [discord.File(io.BytesIO(f.data), filename=f.filename) for f in files]
