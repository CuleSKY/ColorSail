"""Local map subscription tracking for the client scaffold."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

from .notifications import ClickAction, Notification


@dataclass(frozen=True)
class MapSubscription:
    map_name: str
    server_filter: Optional[str] = None


class SubscriptionStore:
    def add(self, subscription: MapSubscription) -> None:
        raise NotImplementedError

    def remove(self, subscription: MapSubscription) -> None:
        raise NotImplementedError

    def list(self) -> List[MapSubscription]:
        raise NotImplementedError


class InMemorySubscriptionStore(SubscriptionStore):
    def __init__(self) -> None:
        self._items: List[MapSubscription] = []

    def add(self, subscription: MapSubscription) -> None:
        if subscription not in self._items:
            self._items.append(subscription)

    def remove(self, subscription: MapSubscription) -> None:
        self._items = [item for item in self._items if item != subscription]

    def list(self) -> List[MapSubscription]:
        return list(self._items)


_DEFAULT_STORE = InMemorySubscriptionStore()


def add_subscription(map_name: str, server_filter_optional: Optional[str] = None) -> None:
    _DEFAULT_STORE.add(MapSubscription(map_name=map_name, server_filter=server_filter_optional))


def remove_subscription(map_name: str, server_filter_optional: Optional[str] = None) -> None:
    _DEFAULT_STORE.remove(MapSubscription(map_name=map_name, server_filter=server_filter_optional))


def list_subscriptions() -> List[MapSubscription]:
    return _DEFAULT_STORE.list()


def _snapshot_by_key(server_snapshot: Iterable[dict]) -> Dict[str, dict]:
    result: Dict[str, dict] = {}
    for entry in server_snapshot:
        key = entry.get("server_key") or entry.get("key") or entry.get("addr")
        if key:
            result[str(key)] = entry
    return result


def _matches_subscription(map_name: str, subscription: MapSubscription, server_key: str) -> bool:
    if subscription.server_filter and subscription.server_filter != server_key:
        return False
    return subscription.map_name.lower() == map_name.lower()


def _build_notification(server_key: str, map_name: str, title: str) -> Notification:
    return Notification(
        title=title,
        message=f"{map_name} is running on {server_key}",
        server_key=server_key,
        map_name=map_name,
        action=ClickAction.ACTION_NONE,
    )


def evaluate_startup_notifications(server_snapshot: Iterable[dict]) -> List[Notification]:
    """Emit one-time notifications for maps currently running at startup."""
    snapshot = _snapshot_by_key(server_snapshot)
    notifications: List[Notification] = []
    for subscription in list_subscriptions():
        for server_key, entry in snapshot.items():
            map_name = entry.get("map") or entry.get("map_name")
            if map_name and _matches_subscription(map_name, subscription, server_key):
                notifications.append(
                    _build_notification(server_key, map_name, "Subscribed map currently running")
                )
    return notifications


def evaluate_refresh_notifications(prev_snapshot: Iterable[dict], new_snapshot: Iterable[dict]) -> List[Notification]:
    """Emit notifications when a server changes to a subscribed map."""
    previous = _snapshot_by_key(prev_snapshot)
    current = _snapshot_by_key(new_snapshot)
    notifications: List[Notification] = []
    for server_key, new_entry in current.items():
        prev_map = (previous.get(server_key) or {}).get("map")
        new_map = new_entry.get("map") or new_entry.get("map_name")
        if not new_map or new_map == prev_map:
            continue
        for subscription in list_subscriptions():
            if _matches_subscription(new_map, subscription, server_key):
                notifications.append(
                    _build_notification(server_key, new_map, "Subscribed map started")
                )
    return notifications
