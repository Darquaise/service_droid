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
    __slots__ = "debug", "guilds_path", "trivia_path", "command_prefix", "owner_ids", "debug_guild_ids"

    def __init__(self):
        print(f"[{dt_now_as_text()}] loading settings...")

        self.debug = _env_bool("DEBUG", False)
        self.command_prefix = os.environ.get("COMMAND_PREFIX", "!")
        self.owner_ids = env_int_list("OWNER_IDS")
        self.debug_guild_ids = env_int_list("DEBUG_GUILD_IDS")

        self.guilds_path = "guilds.json"
        self.trivia_path = "trivia"

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

    def create_guilds_file(self) -> None:
        print(f"[{dt_now_as_text()}] No guilds data found, creating new ones...")
        write_json(self.guilds_path, {})
