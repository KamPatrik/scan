"""
Undo/redo history system for image processing settings.
Provides:
- Full undo/redo stack for processing parameter changes
- History browser
- State snapshots
"""

import logging
import copy
from typing import Optional, List, Callable
from dataclasses import dataclass, field
import datetime

logger = logging.getLogger(__name__)


@dataclass
class HistoryEntry:
    """A single state in the undo/redo history."""
    timestamp: str = ""
    description: str = ""
    settings_snapshot: object = None  # ProcessingSettings copy

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.datetime.now().strftime("%H:%M:%S")


class UndoRedoManager:
    """
    Manages undo/redo history for processing settings.
    """

    def __init__(self, max_history: int = 100):
        self._history: List[HistoryEntry] = []
        self._position: int = -1  # Current position in history
        self._max_history = max_history
        self._batch_active = False
        self._on_change_callback: Optional[Callable] = None

    @property
    def can_undo(self) -> bool:
        return self._position > 0

    @property
    def can_redo(self) -> bool:
        return self._position < len(self._history) - 1

    @property
    def undo_description(self) -> str:
        if self.can_undo:
            return self._history[self._position].description
        return ""

    @property
    def redo_description(self) -> str:
        if self.can_redo:
            return self._history[self._position + 1].description
        return ""

    @property
    def history_count(self) -> int:
        return len(self._history)

    @property
    def current_position(self) -> int:
        return self._position

    def set_change_callback(self, callback: Callable):
        """Set callback to be called when undo/redo state changes."""
        self._on_change_callback = callback

    def push_state(self, settings, description: str = ""):
        """
        Record a new state in the history.
        Truncates any redo history beyond current position.
        """
        if self._batch_active:
            return

        # Deep copy the settings
        snapshot = copy.deepcopy(settings)

        entry = HistoryEntry(
            description=description or "Setting changed",
            settings_snapshot=snapshot,
        )

        # Truncate redo history
        if self._position < len(self._history) - 1:
            self._history = self._history[:self._position + 1]

        self._history.append(entry)

        # Trim if exceeding max
        if len(self._history) > self._max_history:
            excess = len(self._history) - self._max_history
            self._history = self._history[excess:]

        self._position = len(self._history) - 1

        if self._on_change_callback:
            self._on_change_callback()

        logger.debug(
            f"History push: '{description}' (pos={self._position}, "
            f"total={len(self._history)})"
        )

    def undo(self) -> Optional[object]:
        """
        Undo to previous state. Returns the settings snapshot to restore.
        """
        if not self.can_undo:
            return None

        self._position -= 1
        entry = self._history[self._position]

        if self._on_change_callback:
            self._on_change_callback()

        logger.debug(f"Undo to: '{entry.description}' (pos={self._position})")
        return copy.deepcopy(entry.settings_snapshot)

    def redo(self) -> Optional[object]:
        """
        Redo to next state. Returns the settings snapshot to restore.
        """
        if not self.can_redo:
            return None

        self._position += 1
        entry = self._history[self._position]

        if self._on_change_callback:
            self._on_change_callback()

        logger.debug(f"Redo to: '{entry.description}' (pos={self._position})")
        return copy.deepcopy(entry.settings_snapshot)

    def get_history_list(self) -> List[dict]:
        """Get history entries as list of dicts for display."""
        return [
            {
                "index": i,
                "time": e.timestamp,
                "description": e.description,
                "current": i == self._position,
            }
            for i, e in enumerate(self._history)
        ]

    def clear(self):
        """Clear all history."""
        self._history.clear()
        self._position = -1
        if self._on_change_callback:
            self._on_change_callback()

    def begin_batch(self):
        """Start a batch of changes (won't create individual history entries)."""
        self._batch_active = True

    def end_batch(self, settings, description: str = ""):
        """End batch and record final state."""
        self._batch_active = False
        self.push_state(settings, description)
