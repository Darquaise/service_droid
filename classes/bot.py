from discord.ext import bridge

from .settings import Settings


class ServiceDroid(bridge.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = Settings("settings.json")
