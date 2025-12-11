import json
import os
from typing import Any, Optional

import redis


class IngestionQueue:
    """Thin wrapper around Redis list for passing ASR payloads."""

    def __init__(self, redis_url: str, list_name: str = "asr:events", config_key: str = "asr:config"):
        self.redis_url = redis_url
        self.list_name = list_name
        self.config_key = config_key
        self.client = redis.Redis.from_url(redis_url, decode_responses=False)

    @classmethod
    def from_env(cls) -> Optional["IngestionQueue"]:
        url = os.getenv("REDIS_URL")
        if not url:
            return None
        return cls(url)

    def push(self, payload: dict) -> None:
        self.client.lpush(self.list_name, json.dumps(payload).encode("utf-8"))

    def pop(self, timeout: int = 5) -> Optional[dict]:
        item = self.client.brpop(self.list_name, timeout=timeout)
        if not item:
            return None
        _, raw = item
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def load_config(self) -> dict:
        raw = self.client.get(self.config_key)
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def save_config(self, cfg: dict) -> dict:
        self.client.set(self.config_key, json.dumps(cfg))
        return cfg
