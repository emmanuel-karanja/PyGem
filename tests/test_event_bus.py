import pytest
import asyncio
from app.shared.event_bus import InProcessEventBus
from app.config.logger import BulletproofLogger

logger = BulletproofLogger(name="TestEventBus")

@pytest.mark.asyncio
async def test_eventbus_publish_subscribe():
    bus = InProcessEventBus(logger=logger)
    received = []

    async def handler(payload):
        received.append(payload)

    await bus.subscribe("test.event", handler)
    await bus.publish("test.event", {"msg": "hello"})

    # Wait a short moment for async tasks to complete
    await asyncio.sleep(0.1)
    assert received[0] == {"msg": "hello"}
