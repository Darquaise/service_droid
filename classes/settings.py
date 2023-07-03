from typing import TypedDict

import os

from ios import read_json, write_json
from converters import dt_now_as_text
from .guild import Guild


class SettingData(TypedDict):
    debug: bool
    active: bool
    guilds_path: str
    credentials_path: str
    profile: str


class CredentialData(TypedDict):
    token: str
    client_id: str
    client_secret: str
    redirect_uri: str
    origins: list[str]


class Credentials:
    path: str
    profile: str
    token: str
    client_id: int
    client_secret: str
    redirect_uri: str
    origins: list[str]

    def __init__(self, path: str, profile: str):
        full_data = read_json(path)

        if profile not in full_data:
            raise Exception("Profile not found!")

        data: CredentialData = full_data[profile]

        self.path = path
        self.profile = profile
        self.token = data['token']
        self.client_id = int(data['client_id'])
        self.client_secret = data['client_secret']
        self.redirect_uri = data['redirect_uri']
        self.origins = data['origins']


class Settings:
    path: str
    debug: bool
    active: bool
    guilds_path: str
    credentials: Credentials

    def __init__(self, path: str):
        print(f"[{dt_now_as_text()}] loading settings...")
        self.path = path
        if not os.path.isfile(path):
            self.create_settings_file()

        data: SettingData = read_json(path)

        self.guilds_path = data['guilds_path']
        if not os.path.isfile(self.guilds_path):
            self.create_guilds_file()

        credentials_path = data['credentials_path']
        if not os.path.isfile(credentials_path):
            raise FileNotFoundError("Credentials not found")

        profile = data['profile']

        self.credentials = Credentials(credentials_path, profile)

        # debug
        self.debug = data["debug"]

        # active
        self.active = data["active"]

    def get_guilds_data(self) -> dict:
        return read_json(self.guilds_path)

    def update_settings(self):
        data: SettingData = {
            "debug": self.debug,
            "active": self.active,
            "guilds_path": self.guilds_path,
            "credentials_path": self.credentials.path,
            "profile": self.credentials.profile
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
        data: SettingData = {
            "debug": False,
            "active": True,
            "guilds_path": "guilds.json",
            "credentials_path": "credentials.json",
            "profile": "beta"
        }

        write_json(self.path, data)

    def create_guilds_file(self):
        print(f"[{dt_now_as_text()}] No guilds data found, creating new ones...")
        write_json(self.guilds_path, {})
