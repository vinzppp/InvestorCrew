from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any, Protocol

from investorcrew.models import ReportEvent


class EventStore(Protocol):
    def save_event(
        self,
        run_id: str,
        sequence: int,
        stage: str,
        event_type: str,
        title: str,
        actor: str | None,
        payload: dict[str, Any],
        created_at: str,
    ) -> None:
        ...


class RunEventSink:
    def __init__(self, run_id: str | None = None, store: EventStore | None = None) -> None:
        self.run_id = run_id
        self.store = store
        self._sequence = 0
        self.events: list[ReportEvent] = []

    def record(
        self,
        stage: str,
        event_type: str,
        title: str,
        payload: dict[str, Any] | None = None,
        actor: str | None = None,
    ) -> ReportEvent:
        self._sequence += 1
        event = ReportEvent(
            sequence=self._sequence,
            stage=stage,
            event_type=event_type,
            title=title,
            actor=actor,
            payload=payload or {},
            created_at=datetime.now(UTC).isoformat(),
        )
        self.events.append(event)
        if self.run_id and self.store:
            self.store.save_event(
                run_id=self.run_id,
                sequence=event.sequence,
                stage=event.stage,
                event_type=event.event_type,
                title=event.title,
                actor=event.actor,
                payload=event.payload,
                created_at=event.created_at,
            )
        return event

    def record_dataclass(
        self,
        stage: str,
        event_type: str,
        title: str,
        payload: Any,
        actor: str | None = None,
    ) -> ReportEvent:
        if hasattr(payload, "__dataclass_fields__"):
            data = asdict(payload)
        else:
            data = payload
        return self.record(stage=stage, event_type=event_type, title=title, payload=data, actor=actor)
