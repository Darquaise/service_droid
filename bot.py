from discord.ext import bridge
from datetime import timedelta

from ios import read_json, write_json


class Settings:
    def __init__(self, path: str):
        data = read_json(path)
        self.path = path

        # active
        self.active = data["active"]

        # cooldown
        self.cooldown = self.transform_time(data["cooldown"], data["cooldown_type"])
        self._cooldown = data["cooldown"]
        self._cooldown_type = data["cooldown_type"]

        # channels
        self.allowed_channels = {}
        for channel_data in data["channels"]:
            self.allowed_channels[channel_data["id"]] = channel_data["roles"]

    @staticmethod
    def transform_time(time_amount: int, time_type: str):
        time = None

        if time_type == "days":
            time = timedelta(days=time_amount)
        elif time_type == "hours":
            time = timedelta(hours=time_amount)
        elif time_type == "minutes":
            time = timedelta(minutes=time_amount)
        elif time_type == "seconds":
            time = timedelta(seconds=time_amount)

        return time

    def update_settings(self):
        data = {
            "active": self.active,
            "cooldown": self._cooldown,
            "cooldown_type": self._cooldown_type,
            "channels": [
                {
                    "id": channel_id,
                    "roles": roles
                } for channel_id, roles in self.allowed_channels.items()
            ]
        }
        write_json(self.path, data)


class GoldenBot(bridge.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = Settings("settings.json")
