"""One-time migration: the old JSON files -> PostgreSQL.

Reads ``<DATA_DIR>/guilds.json`` and ``<DATA_DIR>/trivia/*.json`` and writes them
through the very same repositories the bot uses, so the JSON->relational mapping
lives in exactly one place. Run **once per environment** with ``DATABASE_URL``
set and the schema already created (``alembic upgrade head``):

    docker compose run --rm bot python scripts/migrate_json_to_pg.py
    # or locally:  cd backend && uv run python scripts/migrate_json_to_pg.py

Re-runnable: each guild's Galatron history/members are cleared first and every
other write is an upsert/replace, so running it twice does not duplicate data.
Delete this script after the migration is verified.
"""

from __future__ import annotations

import asyncio
import glob
import json
import logging
import os
import sys
from pathlib import Path

# Make the backend package root importable when run as scripts/migrate_json_to_pg.py
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

from classes.trivia import TriviaChannelConfig, TriviaQuestion  # noqa: E402
from classes.trivia_modes import MODE_TIMED, ORDER_RANDOM  # noqa: E402
from store import (  # noqa: E402
    dispose_engine,
    galatron_repo,
    guild_repo,
    init_engine,
    lfg_repo,
    trivia_repo,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)-8s %(message)s")
logger = logging.getLogger("migrate")

DATA_DIR = os.environ.get("DATA_DIR", ".")
GUILDS_PATH = os.path.join(DATA_DIR, "guilds.json")
TRIVIA_DIR = os.path.join(DATA_DIR, "trivia")


async def import_guild(gid: int, g: dict) -> None:
    await guild_repo.ensure_guilds([(gid, g.get("name", str(gid)))])
    # Wipe append-only Galatron data so a re-run does not duplicate it.
    await galatron_repo.clear_galatron(gid)

    ga: dict = g.get("galatron") or {}
    if ga:
        await guild_repo.set_galatron_role(gid, ga.get("role"))
        await guild_repo.set_galatron_chance(gid, ga.get("chance", 0.005))
        await guild_repo.set_galatron_cooldown(gid, int(ga.get("cooldown", 86400)))
        for cid in ga.get("channels", []):
            await galatron_repo.add_channel(gid, int(cid))
        for entry in ga.get("history", []):
            await galatron_repo.append_history(
                gid, int(entry["member_id"]), float(entry["timestamp"])
            )
        last_used: dict[str, float] = ga.get("last_used", {})
        totals: dict[str, int] = ga.get("total_times_used", {})
        member_ids = {int(m) for m in last_used} | {int(m) for m in totals}
        for mid in member_ids:
            lu = last_used.get(str(mid))
            await galatron_repo.upsert_member(
                gid,
                mid,
                total=int(totals.get(str(mid), 0)),
                last_used=float(lu) if lu is not None else None,
            )

    for role in g.get("roles", []):
        await lfg_repo.upsert_host_role(
            gid, int(role["id"]), int(role["cooldown"]), role["cooldown_type"]
        )
    for ch in g.get("channels", []):
        await lfg_repo.set_channel_roles(
            gid, int(ch["id"]), [int(r) for r in ch.get("roles", [])]
        )


async def import_trivia_channels(gid: int, g: dict) -> None:
    """Channel->list mappings; run *after* import_trivia so the FK on
    trivia_channel(guild_id, list_name) is satisfied."""
    for cid_str, cfg in g.get("trivia", {}).get("channels", {}).items():
        config = TriviaChannelConfig(
            int(cid_str),
            cfg["list"],
            cfg["schedule"],
            int(cfg["response"]),
            cfg.get("mode", MODE_TIMED),
            cfg.get("order", ORDER_RANDOM),
            next_index=int(cfg.get("next_index", 0)),
        )
        try:
            await trivia_repo.upsert_channel(gid, config)
        except Exception as e:
            logger.warning(
                "skipping trivia channel %s of guild %s (list %r): %s",
                cid_str, gid, cfg["list"], e,
            )


async def import_trivia(gid: int, data: dict) -> None:
    await guild_repo.ensure_guilds([(gid, str(gid))])  # no-op if already present
    lists = {
        name: [
            TriviaQuestion(
                int(q["id"]),
                q["title"],
                q["question"] if isinstance(q["question"], list) else [q["question"]],
                q["answer"],
                q.get("answer_context", ""),
            )
            for q in questions
        ]
        for name, questions in data.items()
    }
    await trivia_repo.replace_guild(gid, lists)


async def import_pending(data: dict) -> None:
    for cid_str, entry in data.items():
        await trivia_repo.upsert_pending(
            int(cid_str),
            float(entry["due_at"]),
            entry["title"],
            entry.get("question", ""),
            entry["answer"],
            entry.get("answer_context", ""),
        )


async def main() -> None:
    init_engine(os.environ["DATABASE_URL"])
    try:
        guilds: dict[str, dict] = {}
        if os.path.isfile(GUILDS_PATH):
            with open(GUILDS_PATH) as f:
                guilds = json.load(f)
            for gid_str, g in guilds.items():
                await import_guild(int(gid_str), g)
                logger.info("imported guild %s (%s)", gid_str, g.get("name"))
        else:
            logger.warning("no guilds.json at %s", GUILDS_PATH)

        for path in sorted(glob.glob(os.path.join(TRIVIA_DIR, "*.json"))):
            stem = os.path.basename(path)[:-len(".json")]
            with open(path) as f:
                data = json.load(f)
            if stem == "_pending":
                await import_pending(data)
                logger.info("imported %d pending reveal(s)", len(data))
            elif stem.isdigit():
                await import_trivia(int(stem), data)
                logger.info("imported trivia for guild %s (%d list(s))", stem, len(data))

        # Last: channel->list mappings need the lists to exist (deferred FK).
        for gid_str, g in guilds.items():
            await import_trivia_channels(int(gid_str), g)
    finally:
        await dispose_engine()

    logger.info("migration complete")


if __name__ == "__main__":
    asyncio.run(main())
