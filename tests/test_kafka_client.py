import pytest
from unittest.mock import AsyncMock, patch
from app.shared.clients.kafka_client import KafkaClient

@pytest.mark.asyncio
async def test_kafka_produce_consume():
    mock_producer = AsyncMock()
    mock_consumer = AsyncMock()
    mock_consumer.__aiter__.return_value = iter([
        type("Message", (), {"topic": "test", "key": b"default", "value": b'{"msg":"hello"}'})()
    ])

    client = KafkaClient(bootstrap_servers="localhost:9092", topics=["test"])
    client._producer = mock_producer
    client._consumer = mock_consumer
    client._running = True

    # Produce
    await client.produce("test", {"msg": "hello"})
    mock_producer.send_and_wait.assert_called_once()

    # Consume
    async for topic, key, value in client.consume():
        assert topic == "test"
        assert key == "default"
        assert value == {"msg": "hello"}

@pytest.mark.asyncio
async def test_subscribe_to_topics():
    mock_consumer = AsyncMock()
    client = KafkaClient(bootstrap_servers="localhost:9092")
    client._consumer = mock_consumer
    client._running = True

    await client.subscribe_to_topics(["topic1", "topic2"])
    mock_consumer.subscribe.assert_called_once_with(["topic1", "topic2"])

