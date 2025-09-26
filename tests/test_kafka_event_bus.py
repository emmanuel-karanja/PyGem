# tests/test_kafka_event_bus_fixed.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.shared.messaging.transports.kafka_bus import KafkaEventBus

@pytest.mark.asyncio
async def test_kafka_event_bus_publish_subscribe():
    # 1️⃣ Mock KafkaClient with AsyncMock for async methods
    mock_client = MagicMock()
    mock_client.publish = AsyncMock()
    mock_client.subscribe = AsyncMock()

    # 2️⃣ Mock logger and metrics
    mock_logger = MagicMock()
    mock_metrics = MagicMock()

    # 3️⃣ Create KafkaEventBus with mocked client
    bus = KafkaEventBus(kafka_client=mock_client, logger=mock_logger, metrics=mock_metrics)

    # 4️⃣ Test publishing
    payload = {"msg": "hello"}
    await bus.publish("test-topic", payload)
    mock_client.publish.assert_awaited_once_with("test-topic", payload)

    # 5️⃣ Test subscribing
    called = False
    async def callback(message):
        nonlocal called
        called = True
        assert message == payload

    await bus.subscribe("test-topic", callback)
    mock_client.subscribe.assert_awaited_once_with("test-topic", callback)

    # 6️⃣ Manually trigger callback to simulate message delivery
    await callback(payload)
    assert called
