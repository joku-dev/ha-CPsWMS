"""Review queue for uncertain entity resolutions."""

from typing import Dict, List

from .models import ResolutionDecision


class ReviewQueue:
    """Manages pending resolution decisions that require review."""

    def __init__(self):
        self.pending_reviews: Dict[str, ResolutionDecision] = {}

    def add_to_review(self, decision: ResolutionDecision) -> None:
        """Add a decision to the review queue."""
        if decision.review_required:
            self.pending_reviews[decision.decision_id] = decision

    def get_pending_reviews(self) -> List[ResolutionDecision]:
        """Get all pending review decisions."""
        return list(self.pending_reviews.values())

    def accept_decision(self, decision_id: str) -> bool:
        """
        Accept a pending decision.

        Returns:
            True if accepted, False if not found.
        """
        if decision_id in self.pending_reviews:
            # Mark as accepted (could update registry here)
            del self.pending_reviews[decision_id]
            return True
        return False

    def reject_decision(self, decision_id: str) -> bool:
        """
        Reject a pending decision.

        Returns:
            True if rejected, False if not found.
        """
        if decision_id in self.pending_reviews:
            # Could create new entity or handle rejection
            del self.pending_reviews[decision_id]
            return True
        return False

    def get_decision(self, decision_id: str) -> ResolutionDecision | None:
        """Get a specific pending decision."""
        return self.pending_reviews.get(decision_id)