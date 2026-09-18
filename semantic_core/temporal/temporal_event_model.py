"""Temporal event modeling for observations and state changes."""

from datetime import datetime, timezone

from semantic_core.identity.models import Observation


class TemporalEventModel:
    """Builds a lightweight timeline of observations and inferred events."""

    def __init__(self):
        self.events: list[Observation] = []

    def add_observation(self, observation: Observation) -> None:
        """Add an observation to the timeline."""
        if observation.timestamp is None:
            observation.timestamp = datetime.now(timezone.utc)
        self.events.append(observation)

    def get_events(self, start_time: datetime | None = None, end_time: datetime | None = None) -> list[Observation]:
        """Return observations within an optional time window."""
        results = []
        for event in self.events:
            if start_time and event.timestamp and event.timestamp < start_time:
                continue
            if end_time and event.timestamp and event.timestamp > end_time:
                continue
            results.append(event)
        return results

    def infer_event_labels(self, observation: Observation) -> dict[str, str]:
        """Create simple labels for observation events."""
        label = f"{observation.observation_type or 'observation'}:{observation.observation_id}"
        return {
            "label": label,
            "source": observation.source_id,
            "type": observation.observation_type,
        }
