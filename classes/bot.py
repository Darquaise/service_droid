from discord.ext import bridge

from .settings import Settings


class ServiceDroid(bridge.Bot):
    def __init__(self, settings: Settings = None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.settings = settings if settings else Settings("settings.json")
