import json
import pytest
from app.shared.clients import RedisClient
from app.config.logger import logger

# -----------------------------
# Dummy Redis backend
# -----------------------------
class DummyRedis:
    def __init__(self):
        self.store = {}

    async def set(self, key, value, ex=None):
        self.store[key] = value

    async def get(self, key):
        return self.store.get(key)

    async def delete(self, key):
        return self.store.pop(key, None) is not None

    async def exists(self, key):
        return key in self.store

    async def ping(self):
        return True

    async def close(self):
        pass


@pytest.mark.asyncio
async def test_redis_set_get_delete(monkeypatch):
    client = RedisClient(logger=logger)
    client.redis = DummyRedis()  # inject dummy backend

    # Test set
    await client.set("key1", {"foo": "bar"}, ttl=60)
    stored_value = client.redis.store.get("key1")
    assert stored_value == json.dumps({"foo": "bar"})

    # Test get
    value = await client.get("key1")
    assert value == {"foo": "bar"}  # JSON is deserialized

    # Test exists
    exists = await client.exists("key1")
    assert exists is True

    # Test delete
    deleted = await client.delete("key1")
    assert deleted is True

    # Test get after delete
    value_after_delete = await client.get("key1")
    assert value_after_delete is None  # ✅ now passes
