import os
from datetime import timedelta

from ios import read_json, write_json
from converters import dt_now_as_text


class Settings:
    def __init__(self, path: str):
        print(f"[{dt_now_as_text()}] loading settings...")
        self.path = path
        if not os.path.isfile(path):
            self.create_file()

        data = read_json(path)

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
        print(f"[{dt_now_as_text()}] settings updated")

    def create_file(self):
        print(f"[{dt_now_as_text()}] No settings found, creating new ones...")
        data = {
            "active": True,
            "cooldown": 3,
            "cooldown_type": "hours",
            "channels": []
        }

        write_json(self.path, data)
