from typing import Any

import discord


def option(*args: Any, **kwargs: Any) -> Any:
    return discord.Option(*args, **kwargs)
