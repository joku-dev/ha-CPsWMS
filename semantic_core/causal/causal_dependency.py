"""Causal dependency graph for semantic reasoning."""



class CausalDependencyGraph:
    """Represents causal relationships between semantic entities."""

    def __init__(self):
        self.dependencies: dict[str, list[str]] = {}

    def add_dependency(self, cause: str, effect: str) -> None:
        """Register a directional causal dependency."""
        self.dependencies.setdefault(cause, []).append(effect)

    def get_effects(self, cause: str) -> list[str]:
        """Return direct effects of a cause."""
        return self.dependencies.get(cause, [])

    def is_causal_path(self, start: str, target: str, visited: list[str] | None = None) -> bool:
        """Determine whether there is a causal path from start to target."""
        if visited is None:
            visited = []
        if start == target:
            return True
        if start in visited:
            return False
        visited.append(start)

        for effect in self.get_effects(start):
            if self.is_causal_path(effect, target, visited):
                return True
        return False

    def get_causal_chain(self, start: str, target: str) -> list[str]:
        """Return one causal chain from start to target, if present."""
        if start == target:
            return [start]

        for effect in self.get_effects(start):
            chain = self.get_causal_chain(effect, target)
            if chain:
                return [start] + chain
        return []
