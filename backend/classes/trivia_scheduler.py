from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import discord

from .trivia import TriviaChannelConfig, TriviaHandler, TriviaQuestion
from .trivia_modes import (
    MODE_AI,
    MODE_AI_TIMED,
    MODE_TIMED,
    ORDER_SEQUENTIAL,
)

if TYPE_CHECKING:
    from .bot import ServiceDroid

logger = logging.getLogger(__name__)


def _log(msg: str) -> None:
    logger.info("[trivia] %s", msg)


class TriviaScheduler:
    __slots__ = ("bot", "_question_tasks", "_answer_tasks")

    def __init__(self, bot: "ServiceDroid"):
        self.bot = bot
        self._question_tasks: dict[int, asyncio.Task] = {}
        self._answer_tasks: dict[int, asyncio.Task] = {}

    def schedule_channel(self, channel_id: int, config: TriviaChannelConfig) -> None:
        self.cancel_channel(channel_id)
        task = self.bot.loop.create_task(
            self._loop_for_channel(channel_id, config),
            name=f"trivia-loop-{channel_id}",
        )
        self._question_tasks[channel_id] = task

    def cancel_channel(self, channel_id: int) -> None:
        task = self._question_tasks.pop(channel_id, None)
        if task is not None and not task.done():
            task.cancel()
        answer = self._answer_tasks.pop(channel_id, None)
        if answer is not None and not answer.done():
            answer.cancel()

    def cancel_all(self) -> None:
        for cid in list(self._question_tasks):
            self.cancel_channel(cid)

    async def _loop_for_channel(self, channel_id: int, config: TriviaChannelConfig) -> None:
        try:
            await self._deliver_pending(channel_id, config)

            while True:
                now = datetime.now(timezone.utc)
                try:
                    next_fire = config.next_fire(now)
                except Exception as e:
                    _log(f"channel {channel_id}: invalid cron `{config.schedule}` ({e}); stopping loop")
                    return

                sleep_seconds = max(0.0, (next_fire - now).total_seconds())
                await asyncio.sleep(sleep_seconds)

                try:
                    await self._fire(channel_id, config)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    _log(f"channel {channel_id}: error firing question: {e!r}")
                    # keep looping — next iteration recomputes the next cron tick
        except asyncio.CancelledError:
            pass

    async def _deliver_pending(self, channel_id: int, config: TriviaChannelConfig) -> None:
        pending = config.pending
        if pending is None:
            return

        now_ts = datetime.now(timezone.utc).timestamp()
        remaining = pending["due_at"] - now_ts

        if remaining <= 0:
            _log(f"channel {channel_id}: pending reveal due {-remaining:.0f}s ago, discarding")
            config.clear_pending()
            self.bot.settings.update_trivia_pending()
            return

        await asyncio.sleep(remaining)

        channel = self.bot.get_channel(channel_id)
        if not isinstance(channel, discord.TextChannel):
            _log(f"channel {channel_id}: not accessible for pending reveal, discarding")
            config.clear_pending()
            self.bot.settings.update_trivia_pending()
            return

        description = f"**{pending['answer']}**"
        if pending.get("answer_context"):
            description += f"\n\n{pending['answer_context']}"
        embed = discord.Embed(
            title=f"Answer: {pending['title']}",
            description=description,
            colour=0x2ecc71,
        )
        try:
            await asyncio.shield(channel.send(embed=embed))
        except asyncio.CancelledError:
            config.clear_pending()
            self.bot.settings.update_trivia_pending()
            raise
        except Exception as e:
            _log(f"channel {channel_id}: failed to send pending reveal: {e!r}")
        config.clear_pending()
        self.bot.settings.update_trivia_pending()

    async def _fire(self, channel_id: int, config: TriviaChannelConfig) -> None:
        channel = self.bot.get_channel(channel_id)
        if channel is None or not isinstance(channel, discord.TextChannel):
            _log(f"channel {channel_id}: not accessible, skipping")
            return

        handler = TriviaHandler.get(channel.guild.id)
        if handler is None or not handler.has_list(config.list_name):
            _log(f"channel {channel_id}: list `{config.list_name}` missing, skipping")
            return

        questions = handler.lists[config.list_name]
        if not questions:
            _log(f"channel {channel_id}: list `{config.list_name}` is empty, skipping")
            return

        question = self._pick_question(config, questions)
        if config.order == ORDER_SEQUENTIAL:
            self.bot.settings.update_guilds()

        if config.mode == MODE_TIMED:
            await self._fire_timed(channel, config, question)
        elif config.mode in (MODE_AI, MODE_AI_TIMED):
            # not implemented yet — fall back to timed reveal so nothing breaks
            _log(f"channel {channel_id}: mode `{config.mode}` not implemented, falling back to timed")
            await self._fire_timed(channel, config, question)
        else:
            _log(f"channel {channel_id}: unknown mode `{config.mode}`, skipping")

    @staticmethod
    def _pick_question(
            config: TriviaChannelConfig, questions: list[TriviaQuestion]
    ) -> TriviaQuestion:
        if config.order == ORDER_SEQUENTIAL:
            return questions[config.next_index(len(questions))]
        return random.choice(questions)

    # -- TIMED mode ----------------------------------------------------------

    async def _fire_timed(
            self, channel: discord.TextChannel, config: TriviaChannelConfig, question: TriviaQuestion,
    ) -> None:
        wording = random.choice(question.question) if question.question else ""
        embed = discord.Embed(
            title=f"Trivia: {question.title}",
            description=wording,
            colour=0xffd700,
        )
        embed.set_footer(text=f"Answer in {config.response}s")
        await channel.send(embed=embed)

        due_at = datetime.now(timezone.utc).timestamp() + config.response
        config.set_pending(due_at, question)
        self.bot.settings.update_trivia_pending()

        # Schedule the answer reveal as its own one-shot task — when it finishes,
        # the question loop is already waiting for the next cron tick.
        prev = self._answer_tasks.pop(channel.id, None)
        if prev is not None and not prev.done():
            prev.cancel()

        task = self.bot.loop.create_task(
            self._reveal_answer(channel, config, question),
            name=f"trivia-answer-{channel.id}",
        )
        self._answer_tasks[channel.id] = task

    async def _reveal_answer(
            self, channel: discord.TextChannel, config: TriviaChannelConfig, question: TriviaQuestion,
    ) -> None:
        try:
            await asyncio.sleep(config.response)
        except asyncio.CancelledError:
            # Cancelled before the answer was sent: leave pending for the next run.
            self._answer_tasks.pop(channel.id, None)
            raise

        description = f"**{question.answer}**"
        if question.answer_context:
            description += f"\n\n{question.answer_context}"
        embed = discord.Embed(
            title=f"Answer: {question.title}",
            description=description,
            colour=0x2ecc71,
        )
        try:
            # Shield: if a cancel arrives mid-send, wait for the send to
            # finish before propagating, so pending can be cleared atomically.
            await asyncio.shield(channel.send(embed=embed))
        except asyncio.CancelledError:
            config.clear_pending()
            self.bot.settings.update_trivia_pending()
            self._answer_tasks.pop(channel.id, None)
            raise
        except Exception as e:
            _log(f"channel {channel.id}: failed to send answer: {e!r}")

        config.clear_pending()
        self.bot.settings.update_trivia_pending()
        self._answer_tasks.pop(channel.id, None)