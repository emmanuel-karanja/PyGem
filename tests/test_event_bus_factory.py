import pytest
from app.shared.messaging.event_bus_factory import EventBusFactory


@pytest.mark.asyncio
async def test_event_bus_factory_inmemory(monkeypatch):
    # Patch config loader to force "memory"
    monkeypatch.setattr(EventBusFactory, "load_config", lambda: {"messaging": {"eventbus": {"transport": "memory"}}})

    bus = EventBusFactory().create_event_bus()
    assert bus is not None

@pytest.mark.asyncio
async def test_event_bus_factory_singleton(monkeypatch):
    monkeypatch.setattr(EventBusFactory, "load_config", lambda: {"messaging": {"eventbus": {"transport": "memory"}}})
    bus1 = EventBusFactory().create_event_bus()
    bus2 = EventBusFactory().create_event_bus()
    assert bus1 is bus2  # Singleton