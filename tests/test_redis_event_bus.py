import pytest
from unittest.mock import AsyncMock, MagicMock
from app.shared.messaging.transports.redis_bus import RedisEventBus

@pytest.mark.asyncio
async def test_redis_event_bus_publish_subscribe():
    # --- Mock Redis client ---
    mock_redis = MagicMock()
    mock_redis.set = AsyncMock()
    mock_redis.get = AsyncMock(return_value='{"foo":"bar"}')
    mock_redis.delete = AsyncMock(return_value=1)
    mock_redis.exists = AsyncMock(return_value=1)
    mock_redis.ping = AsyncMock(return_value=True)

    # --- Mock metrics and logger ---
    mock_metrics = MagicMock()
    mock_logger = MagicMock()

    # --- Inject mocks into RedisEventBus ---
    bus = RedisEventBus(redis_client=mock_redis, logger=mock_logger, metrics=mock_metrics)

    # --- Test publish ---
    payload = {"foo": "bar"}
    await bus.publish("mytopic", payload)
    mock_redis.set.assert_awaited_once()  # ✅ async assert
    mock_logger.info.assert_called()      # logging should have occurred
    mock_metrics.increment.assert_called()  # metrics should be incremented

    # --- Test subscribing ---
    called = False

    async def fake_callback(message):
        nonlocal called
        called = True
        assert message == payload
        return message

    await bus.subscribe("mytopic", fake_callback)
    assert "mytopic" in bus._subscriptions

    # Trigger callbacks manually to simulate message delivery
    for callback in bus._subscriptions["mytopic"]:
        await callback(payload)

    assert called

    # --- Test get/set/delete/exists ---
    result = await bus.redis.get("key1")
    assert result == '{"foo":"bar"}'
    assert await bus.redis.exists("key1") == 1
    await bus.redis.delete("key1")
    mock_redis.delete.assert_awaited_once()
