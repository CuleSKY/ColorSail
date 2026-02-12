import json
from typing import Any, Optional

import redis

from tools.map_sidecar.config import Settings


class RedisCache:
    def __init__(self, settings: Settings) -> None:
        if settings.redis_url:
            self.client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
        elif settings.redis_host and settings.redis_port:
            self.client = redis.Redis(
                host=settings.redis_host,
                port=settings.redis_port,
                password=settings.redis_password,
                decode_responses=True,
            )
        else:
            self.client = None

    def get(self, key: str) -> Optional[str]:
        if not self.client:
            return None
        return self.client.get(key)

    def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        if not self.client:
            return
        self.client.set(key, value, ex=ex)

    def get_json(self, key: str) -> Optional[Any]:
        raw = self.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def set_json(self, key: str, value: Any, ex: Optional[int] = None) -> None:
        payload = json.dumps(value, ensure_ascii=False)
        self.set(key, payload, ex=ex)
