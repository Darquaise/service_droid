from typing import TypedDict
import os

from ios import read_json, write_json
from converters import dt_now_as_text
from .guild import Guild
from .trivia import TriviaHandler


class SettingData(TypedDict):
    debug: bool
    active: bool
    guilds_path: str
    trivia_path: str


class Settings:
    __slots__ = "path", "debug", "active", "guilds_path", "trivia_path"

    def __init__(self, path: str):
        print(f"[{dt_now_as_text()}] loading settings...")
        self.path = path
        if not os.path.isfile(path):
            self.create_settings_file()

        data: SettingData = read_json(path)

        self.guilds_path = data['guilds_path']
        if not os.path.isfile(self.guilds_path):
            self.create_guilds_file()

        self.trivia_path = data.get('trivia_path', "trivia")
        os.makedirs(self.trivia_path, exist_ok=True)

        # debug
        self.debug = data["debug"]

        # active
        self.active = data["active"]

    def get_guilds_data(self) -> dict:
        return read_json(self.guilds_path)

    def to_dict(self) -> SettingData:
        return {
            "debug": self.debug,
            "active": self.active,
            "guilds_path": self.guilds_path,
            "trivia_path": self.trivia_path,
        }
    
    @staticmethod
    def get_live_guilds_dict() -> dict:
        return {guild.id: guild.to_json() for guild in Guild.get_all()}

    @staticmethod
    def get_live_trivia_dict(guild_id: int) -> dict | None:
        handler = TriviaHandler.get(guild_id)
        if handler is None:
            return None
        return handler.to_json()

    def update_settings(self):
        write_json(self.path, self.to_dict())
        print(f"[{dt_now_as_text()}] settings updated")

    def update_guilds(self):
        write_json(self.guilds_path, self.get_live_guilds_dict())
        print(f"[{dt_now_as_text()}] guild settings updated")

    def update_trivia(self, guild_id: int):
        handler = TriviaHandler.get(guild_id)
        if handler is None:
            return
        handler.save(self.trivia_path)
        print(f"[{dt_now_as_text()}] trivia for guild {guild_id} updated")

    def create_settings_file(self):
        print(f"[{dt_now_as_text()}] No settings found, creating new ones...")
        data: SettingData = {
            "debug": False,
            "active": True,
            "guilds_path": "guilds.json",
            "trivia_path": "trivia"
        }

        write_json(self.path, data)

    def create_guilds_file(self):
        print(f"[{dt_now_as_text()}] No guilds data found, creating new ones...")
        write_json(self.guilds_path, {})
