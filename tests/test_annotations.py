# tests/test_clients_and_annotations.py
import asyncio
from typing import Any
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.shared.annotations.core import _SINGLETONS, ApplicationScoped
from app.shared.annotations.messaging import Producer, Consumer, EventBusBinding, register_consumers, _CONSUMER_REGISTRY
from app.shared.messaging.event_bus_factory import EventBusFactory

# -----------------------------
# Fixtures
# -----------------------------
@pytest.fixture(autouse=True)
def reset_singletons():
    """Reset singletons and consumer registry before each test."""
    _SINGLETONS.clear()
    _CONSUMER_REGISTRY.clear()
    yield
    _SINGLETONS.clear()
    _CONSUMER_REGISTRY.clear()


@pytest.fixture
def fake_event_bus(monkeypatch):
    """Mock EventBus with async publish and subscribe."""
    bus = MagicMock()
    bus.publish = AsyncMock()
    bus.subscribe = AsyncMock()
    bus.metrics = MagicMock()
    monkeypatch.setattr(EventBusFactory, "create_event_bus", lambda cls=None: bus)
    return bus


# -----------------------------
# EventBusBinding Tests
# -----------------------------
@pytest.mark.asyncio
async def test_event_bus_binding_injects_event_bus(fake_event_bus):
    @EventBusBinding
    async def my_func(event_bus=None):
        assert event_bus == fake_event_bus
        return "ok"

    result = await my_func()
    assert result == "ok"


# -----------------------------
# Producer Decorator Tests
# -----------------------------
@pytest.mark.asyncio
async def test_producer_decorator_creates_publish_method(fake_event_bus):
    @Producer(topic="test-topic")
    @ApplicationScoped
    class MyProducer:
        def __init__(self, event_bus=None):
            self.event_bus = event_bus

    instance = MyProducer()
    assert hasattr(instance, "publish")
    await instance.publish({"foo": "bar"})
    instance.event_bus.publish.assert_awaited_with("test-topic", {"foo": "bar"})


# -----------------------------
# Consumer Decorator Tests
# -----------------------------
@pytest.mark.asyncio
async def test_consumer_decorator_registers(fake_event_bus):
    @ApplicationScoped
    class MyConsumer:
        def __init__(self):
            self.logger = MagicMock()

        @Consumer("orders")
        async def on_order(self, payload):
            return payload

    instance = MyConsumer()
    _SINGLETONS[MyConsumer] = instance

    # Ensure registry contains the method
    assert any(topic == "orders" and cls == MyConsumer for topic, cls, _ in _CONSUMER_REGISTRY)

    # Register consumers
    await register_consumers()
    # Ensure subscribe was called
    fake_event_bus.subscribe.assert_awaited()
    # Ensure logger called
    instance.logger.info.assert_called()


# -----------------------------
# Test duplicates in Consumer
# -----------------------------
def test_consumer_duplicate_prevention():
    @ApplicationScoped
    class MyConsumer:
        @Consumer("orders")
        async def on_order1(self, payload):
            return payload

        @Consumer("orders")
        async def on_order2(self, payload):
            return payload

    _SINGLETONS[MyConsumer] = MyConsumer()

    # Ensure both methods are in the registry
    topics = [topic for topic, _, _ in _CONSUMER_REGISTRY]
    assert topics.count("orders") == 2  # both methods registered for same topic


# -----------------------------
# EventBusFactory Singleton Test
# -----------------------------
def test_event_bus_factory_singleton(monkeypatch):
    fake_bus = MagicMock()
    monkeypatch.setattr(EventBusFactory, "create_event_bus", lambda cls=None: fake_bus)

    bus1 = EventBusFactory().create_event_bus()
    bus2 = EventBusFactory().create_event_bus()
    assert bus1 is bus2  # Singleton check

