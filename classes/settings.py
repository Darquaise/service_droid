import os

from ios import read_json, write_json
from converters import dt_now_as_text
from .guild import Guild


class Settings:
    __slots__ = "path", "debug", "active", "guilds_path"

    def __init__(self, path: str):
        print(f"[{dt_now_as_text()}] loading settings...")
        self.path = path
        if not os.path.isfile(path):
            self.create_settings_file()

        data = read_json(path)

        self.guilds_path = data['guilds_path']
        if not os.path.isfile(self.guilds_path):
            self.create_guilds_file()

        # debug
        self.debug = data["debug"]

        # active
        self.active = data["active"]

    def get_guilds_data(self) -> dict:
        return read_json(self.guilds_path)

    def update_settings(self):
        data = {
            "debug": self.debug,
            "active": self.active,
            "guilds_path": self.guilds_path
        }
        write_json(self.path, data)
        print(f"[{dt_now_as_text()}] settings updated")

    def update_guilds(self):
        data = {}
        for guild in Guild.get_all():
            data[guild.id] = guild.to_json()
        write_json(self.guilds_path, data)
        print(f"[{dt_now_as_text()}] guild settings updated")

    def create_settings_file(self):
        print(f"[{dt_now_as_text()}] No settings found, creating new ones...")
        data = {
            "debug": False,
            "active": True,
            "guilds_path": "guilds.json"
        }

        write_json(self.path, data)

    def create_guilds_file(self):
        print(f"[{dt_now_as_text()}] No guilds data found, creating new ones...")
        write_json(self.guilds_path, {})
