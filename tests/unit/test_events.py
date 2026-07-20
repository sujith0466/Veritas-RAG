"""Unit tests for the internal async event dispatcher and event domain objects."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest

from backend.core.events import BaseEvent, EventDispatcher, EventType, get_dispatcher


@dataclass(frozen=True)
class DummyEvent(BaseEvent):
    document_id: str = "doc_123"
    tenant_id: str = "tenant_abc"


@pytest.mark.unit
class TestBaseEventAndEventType:
    def test_base_event_defaults_and_immutability(self) -> None:
        event = DummyEvent(event_type=EventType.DOCUMENT_UPLOADED)
        assert event.event_type == EventType.DOCUMENT_UPLOADED
        assert event.event_id is not None
        assert isinstance(event.occurred_at, datetime)
        assert event.occurred_at.tzinfo == UTC
        assert event.document_id == "doc_123"
        assert event.tenant_id == "tenant_abc"

        with pytest.raises(Exception):  # FrozenInstanceError / AttributeError
            event.document_id = "new_doc"  # type: ignore[misc]

    def test_to_dict_serialization(self) -> None:
        event = DummyEvent(
            event_type=EventType.DOCUMENT_UPLOADED,
            correlation_id="corr-999",
        )
        data = event.to_dict()
        assert data["event_id"] == event.event_id
        assert data["event_type"] == "document.uploaded"
        assert data["occurred_at"] == event.occurred_at.isoformat()
        assert data["correlation_id"] == "corr-999"

    def test_event_types_exist(self) -> None:
        assert EventType.DOCUMENT_UPLOADED.value == "document.uploaded"
        assert EventType.RETRY_TRIGGERED.value == "retry.triggered"
        assert EventType.SYSTEM_STARTUP_COMPLETED.value == "system.startup_completed"


@pytest.mark.unit
class TestEventDispatcher:
    @pytest.fixture
    def dispatcher(self) -> EventDispatcher:
        return EventDispatcher()

    @pytest.mark.asyncio
    async def test_subscribe_publish_and_handler_count(self, dispatcher: EventDispatcher) -> None:
        received_events: list[BaseEvent] = []

        async def handler_a(event: BaseEvent) -> None:
            received_events.append(event)

        async def handler_b(event: BaseEvent) -> None:
            received_events.append(event)

        assert dispatcher.handler_count(EventType.DOCUMENT_UPLOADED) == 0

        dispatcher.subscribe(EventType.DOCUMENT_UPLOADED, handler_a)
        dispatcher.subscribe(EventType.DOCUMENT_UPLOADED, handler_b)
        assert dispatcher.handler_count(EventType.DOCUMENT_UPLOADED) == 2

        event = DummyEvent(event_type=EventType.DOCUMENT_UPLOADED)
        await dispatcher.publish(event)

        assert len(received_events) == 2
        assert event in received_events

    @pytest.mark.asyncio
    async def test_unsubscribe(self, dispatcher: EventDispatcher) -> None:
        received: list[BaseEvent] = []

        async def handler(event: BaseEvent) -> None:
            received.append(event)

        dispatcher.subscribe(EventType.QUERY_RECEIVED, handler)
        assert dispatcher.handler_count(EventType.QUERY_RECEIVED) == 1

        dispatcher.unsubscribe(EventType.QUERY_RECEIVED, handler)
        assert dispatcher.handler_count(EventType.QUERY_RECEIVED) == 0

        await dispatcher.publish(DummyEvent(event_type=EventType.QUERY_RECEIVED))
        assert len(received) == 0

    @pytest.mark.asyncio
    async def test_publish_with_no_subscribers_does_not_raise(self, dispatcher: EventDispatcher) -> None:
        event = DummyEvent(event_type=EventType.RETRIEVAL_COMPLETED)
        # Should complete silently without error
        await dispatcher.publish(event)

    @pytest.mark.asyncio
    async def test_publish_isolates_handler_exceptions(self, dispatcher: EventDispatcher) -> None:
        successful_executions = []

        async def failing_handler(event: BaseEvent) -> None:
            raise ValueError("Handler crashed!")

        async def succeeding_handler(event: BaseEvent) -> None:
            successful_executions.append(event)

        dispatcher.subscribe(EventType.EVALUATION_STARTED, failing_handler)
        dispatcher.subscribe(EventType.EVALUATION_STARTED, succeeding_handler)

        event = DummyEvent(event_type=EventType.EVALUATION_STARTED)
        # Should not raise despite failing_handler throwing ValueError
        await dispatcher.publish(event)

        assert len(successful_executions) == 1
        assert successful_executions[0] == event

    @pytest.mark.asyncio
    async def test_publish_concurrent_execution(self, dispatcher: EventDispatcher) -> None:
        start_times = []
        end_times = []

        async def slow_handler_1(event: BaseEvent) -> None:
            start_times.append(asyncio.get_running_loop().time())
            await asyncio.sleep(0.05)
            end_times.append(asyncio.get_running_loop().time())

        async def slow_handler_2(event: BaseEvent) -> None:
            start_times.append(asyncio.get_running_loop().time())
            await asyncio.sleep(0.05)
            end_times.append(asyncio.get_running_loop().time())

        dispatcher.subscribe(EventType.VALIDATION_COMPLETED, slow_handler_1)
        dispatcher.subscribe(EventType.VALIDATION_COMPLETED, slow_handler_2)

        start = asyncio.get_running_loop().time()
        await dispatcher.publish(DummyEvent(event_type=EventType.VALIDATION_COMPLETED))
        total_duration = asyncio.get_running_loop().time() - start

        # If sequential, duration would be >= 0.10. If concurrent via gather, should be ~0.05
        assert total_duration < 0.09
        assert len(start_times) == 2
        assert len(end_times) == 2

    def test_get_dispatcher_singleton(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import backend.core.events.dispatcher as disp_mod
        monkeypatch.setattr(disp_mod, "_dispatcher", None)

        d1 = get_dispatcher()
        d2 = get_dispatcher()
        assert d1 is d2
