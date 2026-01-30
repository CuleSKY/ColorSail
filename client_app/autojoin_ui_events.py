"""UI event handling scaffold for AutoJoin."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Tuple

from .autojoin_core import AutoJoinState


class UIEvent(str, Enum):
    PANEL_OPEN = "PANEL_OPEN"
    PANEL_CLOSE = "PANEL_CLOSE"
    USER_STOP = "USER_STOP"
    USER_JOIN_SERVER = "USER_JOIN_SERVER"
    USER_COPY_CONSOLE = "USER_COPY_CONSOLE"
    USER_EXIT_APP = "USER_EXIT_APP"
    CORE_ERROR = "CORE_ERROR"


class UIActionType(str, Enum):
    CONFIRM = "CONFIRM"
    STOP_CORE = "STOP_CORE"
    SHOW_FLOATING_WIDGET = "SHOW_FLOATING_WIDGET"
    HIDE_FLOATING_WIDGET = "HIDE_FLOATING_WIDGET"
    SHOW_TOAST = "SHOW_TOAST"


@dataclass(frozen=True)
class UIAction:
    action: UIActionType
    message: str | None = None


@dataclass
class UIState:
    panel_open: bool = True
    core_state: AutoJoinState = AutoJoinState.IDLE


def handle_user_event(current_state: UIState, event: UIEvent) -> Tuple[UIState, List[UIAction]]:
    """Return the next UI state and any UI actions triggered by the event."""
    next_state = UIState(panel_open=current_state.panel_open, core_state=current_state.core_state)
    actions: List[UIAction] = []

    if event == UIEvent.PANEL_OPEN:
        next_state.panel_open = True
        actions.append(UIAction(UIActionType.HIDE_FLOATING_WIDGET))
    elif event == UIEvent.PANEL_CLOSE:
        next_state.panel_open = False
        if current_state.core_state == AutoJoinState.RUNNING:
            actions.append(UIAction(UIActionType.SHOW_FLOATING_WIDGET))
    elif event == UIEvent.USER_STOP:
        actions.append(UIAction(UIActionType.STOP_CORE))
        next_state.core_state = AutoJoinState.STOPPED
    elif event in {UIEvent.USER_JOIN_SERVER, UIEvent.USER_COPY_CONSOLE, UIEvent.USER_EXIT_APP}:
        actions.append(UIAction(UIActionType.CONFIRM, "Confirm interrupting AutoJoin"))
    elif event == UIEvent.CORE_ERROR:
        next_state.core_state = AutoJoinState.ERROR
        actions.append(UIAction(UIActionType.SHOW_TOAST, "AutoJoin encountered an error"))

    return next_state, actions
