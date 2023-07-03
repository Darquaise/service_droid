import os
from datetime import datetime, timedelta

from ios import read_json, write_json

from .typing_classes import TokenResponse, TokenStorage


class TokenDB:
    path: str
    current_data: dict
    last_update: datetime

    def __init__(self, path: str = 'routers/tokens.json'):
        self.path = path
        self.current_data = read_json(path)
        self.last_update = datetime.utcnow()

    def check_for_update(self) -> bool:
        last_update = datetime.fromtimestamp(os.path.getmtime(self.path))
        if last_update > self.last_update:
            self.current_data = read_json(self.path)
            self.last_update = last_update
            return True
        return False

    def update(self) -> None:
        write_json(self.path, self.current_data)

    def get_entry(self, user_id: int | str) -> TokenStorage | None:
        return self.current_data.get(str(user_id))

    def set_entry(self, user_id: int | str, token_payload: TokenResponse, expires_at: int = None) -> None:
        self.check_for_update()

        data: TokenStorage = {
            "access_token": token_payload.get("access_token"),
            "token_expires_at": int(
                (datetime.utcnow() + timedelta(seconds=int(token_payload.get("expires_in")))).timestamp()),
            "refresh_token": token_payload.get("refresh_token")
        }
        if expires_at:
            data["access_token_expires_at"] = expires_at

        self.current_data[str(user_id)] = data
        self.update()

    def remove_entry(self, user_id: int | str) -> bool:
        if str(user_id) in self.current_data:
            del self.current_data[str(user_id)]
            self.update()
            return True
        return False
