from __future__ import annotations

from typing import Dict


class AutoJoinService:
    def __init__(self, queue_manager, a2s_cache) -> None:
        self.queue_manager = queue_manager
        self.a2s_cache = a2s_cache

    def enqueue(self, steam_id: str, server_key: str, priority: str, queue_type: str) -> Dict[str, str]:
        self.a2s_cache.ensure_server(server_key)
        return self.queue_manager.enqueue(steam_id, server_key, priority, queue_type)

    def mark_joined(self, queue_id: str, steam_id: str, server_key: str) -> Dict[str, str]:
        return self.queue_manager.mark_joined(queue_id, steam_id, server_key)

    def stop_queue(self, queue_id: str, steam_id: str, server_key: str) -> Dict[str, str]:
        return self.queue_manager.stop_queue(queue_id, steam_id, server_key)

    def get_status(self, server_key: str) -> dict:
        return self.queue_manager.get_status(server_key)
