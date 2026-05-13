"""In-memory observability event store and summary helpers."""

from collections import Counter, defaultdict, deque
from collections.abc import Iterable
from threading import Lock

from app.catalog.registry import CatalogRegistry
from app.models.observability import (
    ConversationDetail,
    ConversationSummary,
    InvocationEvent,
    MonitoringSummary,
    VerticalHealthSummary,
    VerticalMonitoringSummary,
)
from app.models.validation import ToolValidationStatus, ValidationReport

_UNKNOWN_VERTICAL = "unknown"


class ObservabilityStore:
    """Bounded in-memory store for safe invocation metadata.

    This store is intentionally lightweight for the challenge demo. It is not
    persistent and is reset when the process restarts.
    """

    def __init__(self, max_events: int = 1000) -> None:
        if max_events <= 0:
            raise ValueError("max_events must be positive")

        self._events: deque[InvocationEvent] = deque(maxlen=max_events)
        self._lock = Lock()

    def record(self, event: InvocationEvent) -> None:
        """Record one safe invocation event."""
        with self._lock:
            self._events.append(event)

    def list_events(self) -> list[InvocationEvent]:
        """Return all currently retained events in insertion order."""
        with self._lock:
            return list(self._events)

    def monitoring_summary(self) -> MonitoringSummary:
        """Return global and per-vertical call/error/latency totals."""
        events = self.list_events()
        return MonitoringSummary(
            total_calls=len(events),
            successes=sum(1 for event in events if event.ok),
            errors=sum(1 for event in events if not event.ok),
            average_latency_ms=_average_latency(events),
            by_vertical=_summaries_by_vertical(events),
        )

    def vertical_summary(
        self,
        catalog: CatalogRegistry,
        validation_report: ValidationReport | None,
        vertical_names: Iterable[str],
    ) -> list[VerticalHealthSummary]:
        """Return simple health/dashboard status for configured verticals."""
        events = self.list_events()
        monitoring = self.monitoring_summary().by_vertical
        accepted_counts = _accepted_tool_counts(catalog)
        rejected_counts = _rejected_tool_counts(validation_report)
        last_failures = _last_failures_by_vertical(events)

        summaries: list[VerticalHealthSummary] = []
        for name in vertical_names:
            stats = monitoring.get(name, VerticalMonitoringSummary())
            summaries.append(
                VerticalHealthSummary(
                    name=name,
                    reachable=True,
                    accepted_tools=accepted_counts.get(name, 0),
                    rejected_tools=rejected_counts.get(name, 0),
                    calls=stats.calls,
                    errors=stats.errors,
                    last_failure=last_failures.get(name),
                    status=_vertical_status(stats),
                )
            )

        return summaries

    def recent_failures(self, limit: int = 20) -> list[InvocationEvent]:
        """Return most recent failed invocation events, newest first."""
        if limit <= 0:
            return []

        events = self.list_events()
        failures = [event for event in reversed(events) if not event.ok]
        return failures[:limit]

    def conversations(self) -> list[ConversationSummary]:
        """Return summaries for conversations that provided a conversation ID."""
        events_by_conversation = self._events_by_conversation()
        return [
            _conversation_summary(conversation_id, events)
            for conversation_id, events in sorted(events_by_conversation.items())
        ]

    def conversation_detail(self, conversation_id: str) -> ConversationDetail | None:
        """Return detailed usage timeline for one conversation ID."""
        events = self._events_by_conversation().get(conversation_id)
        if not events:
            return None

        summary = _conversation_summary(conversation_id, events)
        return ConversationDetail(**summary.model_dump(), events=events)

    def _events_by_conversation(self) -> dict[str, list[InvocationEvent]]:
        events = self.list_events()
        grouped: dict[str, list[InvocationEvent]] = defaultdict(list)
        for event in events:
            if event.conversation_id:
                grouped[event.conversation_id].append(event)
        return dict(grouped)


def _summaries_by_vertical(events: list[InvocationEvent]) -> dict[str, VerticalMonitoringSummary]:
    grouped: dict[str, list[InvocationEvent]] = defaultdict(list)
    for event in events:
        grouped[event.vertical or _UNKNOWN_VERTICAL].append(event)

    return {
        vertical: VerticalMonitoringSummary(
            calls=len(vertical_events),
            successes=sum(1 for event in vertical_events if event.ok),
            errors=sum(1 for event in vertical_events if not event.ok),
            average_latency_ms=_average_latency(vertical_events),
        )
        for vertical, vertical_events in grouped.items()
    }


def _average_latency(events: list[InvocationEvent]) -> float:
    if not events:
        return 0.0

    return round(sum(event.latency_ms for event in events) / len(events), 2)


def _accepted_tool_counts(catalog: CatalogRegistry) -> Counter[str]:
    counts: Counter[str] = Counter()
    for tool in catalog.list_tools():
        route = catalog.get_route(tool.name)
        if route is not None:
            counts[route.vertical] += 1
    return counts


def _rejected_tool_counts(validation_report: ValidationReport | None) -> Counter[str]:
    counts: Counter[str] = Counter()
    if validation_report is None:
        return counts

    for result in validation_report.results:
        if result.status == ToolValidationStatus.REJECTED:
            counts[result.vertical] += 1
    return counts


def _last_failures_by_vertical(events: list[InvocationEvent]) -> dict[str, InvocationEvent]:
    failures: dict[str, InvocationEvent] = {}
    for event in reversed(events):
        if event.ok or event.vertical is None or event.vertical in failures:
            continue
        failures[event.vertical] = event
    return failures


def _vertical_status(stats: VerticalMonitoringSummary) -> str:
    if stats.calls == 0 or stats.errors == 0:
        return "green"
    if stats.errors == stats.calls:
        return "red"
    return "yellow"


def _conversation_summary(
    conversation_id: str,
    events: list[InvocationEvent],
) -> ConversationSummary:
    tool_counts: Counter[str] = Counter(event.public_tool_name for event in events)
    vertical_counts: Counter[str] = Counter(
        event.vertical for event in events if event.vertical is not None
    )

    return ConversationSummary(
        conversation_id=conversation_id,
        calls=len(events),
        errors=sum(1 for event in events if not event.ok),
        tool_counts=dict(tool_counts),
        vertical_counts=dict(vertical_counts),
        last_seen=max((event.timestamp for event in events), default=None),
    )
