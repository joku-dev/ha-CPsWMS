"""State evolution modeling for tracking transitions over time."""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class StateTransition:
    """A state transition observed for an entity."""
    source_entity_id: str
    previous_state: Optional[str]
    next_state: Optional[str]
    timestamp: datetime
    reason: Optional[str] = None


class StateEvolution:
    """Tracks entity state transitions over time."""

    def __init__(self):
        self.transitions: List[StateTransition] = []

    def add_transition(self, transition: StateTransition) -> None:
        """Add a new state transition to the evolution history."""
        self.transitions.append(transition)

    def get_transitions_for_entity(self, source_entity_id: str) -> List[StateTransition]:
        """Get transitions for a specific source entity."""
        return [t for t in self.transitions if t.source_entity_id == source_entity_id]

    def last_transition(self, source_entity_id: str) -> Optional[StateTransition]:
        """Get the most recent transition for an entity."""
        filtered = self.get_transitions_for_entity(source_entity_id)
        return filtered[-1] if filtered else None
