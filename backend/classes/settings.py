import logging
import os

logger = logging.getLogger(__name__)


def env_int_list(name: str) -> list[int]:
    raw = os.environ.get(name, "")
    return [int(x) for x in raw.split(",") if x.strip()]


class Settings:
    __slots__ = (
        "debug", "database_url", "command_prefix", "owner_ids", "debug_guild_ids",
    )

    def __init__(self):
        logger.info("loading settings...")

        self.debug = os.environ.get("DEBUG", "").strip().lower() == "true"
        self.command_prefix = os.environ.get("COMMAND_PREFIX", "!")
        self.owner_ids = env_int_list("OWNER_IDS")
        self.debug_guild_ids = env_int_list("DEBUG_GUILD_IDS")
        self.database_url = os.environ["DATABASE_URL"]
