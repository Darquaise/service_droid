"""Loading ``.env.e2e`` — must run before any bot module is imported.

``cogs/dev.py`` reads ``DEBUG_GUILD_IDS`` at import time, so the environment has to be complete before
``classes``/``cogs`` are imported. Deliberately never reads the repo's ``.env``: that one may point at
a real token and a real database.
"""

from __future__ import annotations

import base64
import binascii
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = ROOT / ".env.e2e"
DATA_DIR = ROOT / ".dev" / "e2e"

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
THROWAWAY_DB = "service_droid_e2e"
# machine-wide, not per clone: the token can only be logged in once, whichever checkout runs
LOCK_DIR = Path.home() / ".cache" / "service_droid" / "e2e.lock"
REQUIRED = ("DISCORD_TOKEN", "E2E_GUILD_ID", "E2E_DUMMY_USER_IDS", "DATABASE_URL")
# Production bots (Service Droid, Vibebot): logging in with their token would sync the test command set
# over their live slash commands.
FORBIDDEN_BOT_IDS = {1080485809989369856, 701905927363756112}


class E2EConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class E2EConfig:
    token: str
    guild_id: int
    dummy_user_ids: list[int]
    database_url: str


def required_by_runner() -> bool:
    """scripts/e2e.sh (and with it the pre-commit hook) sets this: a missing setup must fail, not skip."""
    return os.environ.get("E2E_REQUIRED") == "1"


def check_throwaway_db(url: str) -> None:
    """The tests wipe guild data: only the throwaway database of scripts/e2e.sh is acceptable."""
    parts = urlsplit(url.replace("postgresql+psycopg://", "postgresql://"))
    if parts.hostname not in LOCAL_HOSTS or parts.path.lstrip("/") != THROWAWAY_DB:
        raise E2EConfigError(
            f"refusing to use DATABASE_URL {parts.hostname}/{parts.path.lstrip('/')}: the tests wipe guild data. "
            f"Only the throwaway database localhost/{THROWAWAY_DB} is allowed — use scripts/e2e.sh."
        )


def check_runner() -> None:
    """Live runs only under scripts/e2e.sh, which holds the lock and checks that the dev bot is down."""
    pid = os.environ.get("E2E_RUNNER_PID", "")
    try:
        locked = (LOCK_DIR / "pid").read_text().strip()
    except OSError:
        locked = ""
    if not pid or pid != locked:
        raise E2EConfigError("live e2e tests run only via scripts/e2e.sh (it holds the run lock)")
    try:
        os.kill(int(pid), 0)
    except (OSError, ValueError):
        raise E2EConfigError("the e2e run lock belongs to a process that is gone — use scripts/e2e.sh") from None


def token_bot_id(token: str) -> int | None:
    """The bot's user id, encoded in the first segment of its token."""
    head = token.strip().split(".", 1)[0]
    try:
        return int(base64.urlsafe_b64decode(head + "=" * (-len(head) % 4)))
    except (binascii.Error, ValueError):
        return None


def load_e2e_env() -> E2EConfig:
    if not ENV_FILE.exists():
        raise E2EConfigError(
            f"{ENV_FILE} is missing — copy .env.e2e.example to .env.e2e and fill it in (see docs/testing.md)"
        )
    # real environment variables win, so scripts/e2e.sh can force the throwaway DATABASE_URL
    load_dotenv(ENV_FILE, override=False)

    missing = [k for k in REQUIRED if not os.environ.get(k, "").strip()]
    if missing:
        hint = " (run via scripts/e2e.sh, which provides the throwaway database)" if "DATABASE_URL" in missing else ""
        raise E2EConfigError(f"missing in {ENV_FILE.name}: {', '.join(missing)}{hint}")

    check_throwaway_db(os.environ["DATABASE_URL"])
    check_runner()

    guild_id = int(os.environ["E2E_GUILD_ID"])
    dummies = [int(x) for x in os.environ["E2E_DUMMY_USER_IDS"].split(",") if x.strip()]
    if len(dummies) < 2:
        raise E2EConfigError("E2E_DUMMY_USER_IDS needs at least 2 user ids (3 recommended)")

    bot_id = token_bot_id(os.environ["DISCORD_TOKEN"])
    if bot_id is None or bot_id in FORBIDDEN_BOT_IDS:
        raise E2EConfigError(
            "refusing to log in: DISCORD_TOKEN is not a recognizable bot token or belongs to a production bot"
        )
    if bot_id in dummies:
        raise E2EConfigError("E2E_DUMMY_USER_IDS must not contain the test bot itself")

    os.environ["DEBUG"] = "true"
    os.environ["DEBUG_GUILD_IDS"] = str(guild_id)
    os.environ["OWNER_IDS"] = ""
    os.environ["DATA_DIR"] = str(DATA_DIR)
    return E2EConfig(os.environ["DISCORD_TOKEN"], guild_id, dummies, os.environ["DATABASE_URL"])
