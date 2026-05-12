"""LLM metric collection helpers.

The current enrichment workers do not persist structured LLM telemetry. This
collector therefore returns explicit null/zero values and warnings unless a
future telemetry source is provided.
"""

from __future__ import annotations

from .metrics_collector import LLMMetrics


class LLMMetricsCollector:
    """Collect LLM metrics without hard-coding a provider-specific dependency."""

    def collect(self) -> tuple[LLMMetrics, list[str]]:
        return LLMMetrics(), [
            "Structured LLM telemetry is not available; token, latency and cost metrics are null or zero."
        ]

