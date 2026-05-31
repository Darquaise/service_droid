import os

from ios import read_json, write_json
from converters import dt_now_as_text
from .guild import Guild
from .trivia import TriviaHandler


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_int_list(name: str) -> list[int]:
    raw = os.environ.get(name, "")
    return [int(x) for x in raw.split(",") if x.strip()]


class Settings:
    __slots__ = (
        "debug", "guilds_path", "trivia_path", "trivia_pending_path",
        "command_prefix", "owner_ids", "debug_guild_ids",
    )

    def __init__(self):
        print(f"[{dt_now_as_text()}] loading settings...")

        self.debug = _env_bool("DEBUG", False)
        self.command_prefix = os.environ.get("COMMAND_PREFIX", "!")
        self.owner_ids = env_int_list("OWNER_IDS")
        self.debug_guild_ids = env_int_list("DEBUG_GUILD_IDS")

        self.guilds_path = "guilds.json"
        self.trivia_path = "trivia"
        self.trivia_pending_path = os.path.join(self.trivia_path, "_pending.json")

        if not os.path.isfile(self.guilds_path):
            self.create_guilds_file()
        os.makedirs(self.trivia_path, exist_ok=True)

    def get_guilds_data(self) -> dict:
        return read_json(self.guilds_path)

    @staticmethod
    def get_live_guilds_dict() -> dict:
        return {guild.id: guild.to_json() for guild in Guild.get_all()}

    @staticmethod
    def get_live_trivia_dict(guild_id: int) -> dict | None:
        handler = TriviaHandler.get(guild_id)
        if handler is None:
            return None
        return handler.to_json()

    def update_guilds(self) -> None:
        write_json(self.guilds_path, self.get_live_guilds_dict())
        print(f"[{dt_now_as_text()}] guild settings updated")

    def update_trivia(self, guild_id: int) -> None:
        handler = TriviaHandler.get(guild_id)
        if handler is None:
            return
        handler.save(self.trivia_path)
        print(f"[{dt_now_as_text()}] trivia for guild {guild_id} updated")

    def load_trivia_pending(self) -> dict:
        if not os.path.isfile(self.trivia_pending_path):
            return {}
        try:
            data = read_json(self.trivia_pending_path)
        except Exception as e:
            print(f"[{dt_now_as_text()}] could not read pending trivia ({e!r}), starting without it")
            return {}
        if not isinstance(data, dict):
            print(f"[{dt_now_as_text()}] pending trivia file is malformed, starting without it")
            return {}
        # Drop entries that don't match the shape _deliver_pending expects, so a
        # corrupt/hand-edited file can never crash the scheduler loop on startup.
        valid: dict[str, dict] = {}
        for cid, entry in data.items():
            if (
                isinstance(entry, dict)
                and isinstance(entry.get("due_at"), (int, float))
                and isinstance(entry.get("title"), str)
                and isinstance(entry.get("answer"), str)
            ):
                valid[cid] = entry
            else:
                print(f"[{dt_now_as_text()}] discarding malformed pending entry for channel {cid}")
        return valid

    def update_trivia_pending(self) -> None:
        pending: dict[str, dict] = {}
        for guild in Guild.get_all():
            for cid, cfg in guild.trivia_channels.items():
                if cfg.pending is not None:
                    pending[str(cid)] = cfg.pending
        write_json(self.trivia_pending_path, pending)

    def create_guilds_file(self) -> None:
        print(f"[{dt_now_as_text()}] No guilds data found, creating new ones...")
        write_json(self.guilds_path, {})
