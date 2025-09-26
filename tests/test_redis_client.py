import pytest
from unittest.mock import AsyncMock
from app.shared.clients.redis_client import RedisClient

import pytest
from unittest.mock import AsyncMock
from app.shared.clients import RedisClient

@pytest.mark.asyncio
async def test_redis_client_set_get(monkeypatch):
    client = RedisClient(redis_url="redis://localhost:6379/0")

    # Mock the Redis connection
    mock_redis = AsyncMock()
    monkeypatch.setattr(client, "redis", mock_redis)

    # Mock ping (if connect calls it)
    mock_redis.ping = AsyncMock(return_value=True)

    # Set and get
    await client.set("mykey", {"foo": "bar"}, ttl=10)
    mock_redis.set.assert_awaited_once_with("mykey", '{"foo": "bar"}', ex=10)

    mock_redis.get = AsyncMock(return_value='{"foo": "bar"}')
    value = await client.get("mykey")
    assert value == {"foo": "bar"}



@pytest.mark.asyncio
async def test_redis_delete_exists():
    mock_redis = AsyncMock()
    mock_redis.delete.return_value = 1
    mock_redis.exists.return_value = 1

    redis_client = RedisClient(redis_url="redis://localhost:6379")
    redis_client.redis = mock_redis

    deleted = await redis_client.delete("foo")
    exists = await redis_client.exists("foo")

    assert deleted is True
    assert exists is True