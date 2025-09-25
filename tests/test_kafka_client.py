import pytest
import asyncio
from app.shared.clients.kafka_client import KafkaClient
from logger import BulletproofLogger
from retry import ExponentialBackoffRetry
import json

logger = BulletproofLogger(name="TestKafkaLogger")

@pytest.mark.asyncio
async def test_produce_consume(monkeypatch):
    produced_messages = []

    # ----------------------------
    # Dummy Producer
    # ----------------------------
    class DummyProducer:
        async def send_and_wait(self, topic, key, value):
            produced_messages.append((topic, key, value))

    # ----------------------------
    # Dummy Consumer
    # ----------------------------
    class DummyConsumer:
        async def start(self): pass
        async def stop(self): pass

        async def __aiter__(self):
            for key, value in produced_messages:
                class Msg:
                    def __init__(self, key, value):
                        self.key = key.encode() if isinstance(key, str) else key
                        self.value = json.dumps(value).encode() if isinstance(value, dict) else value
                yield Msg(key, value)

    # ----------------------------
    # Instantiate KafkaClient with dummy producer/consumer
    # ----------------------------
    client = KafkaClient(
        bootstrap_servers="dummy:9092",
        topic="test_topic",
        dlq_topic="test_dlq",
        group_id="test_group",
        logger=logger,
        retry_policy=ExponentialBackoffRetry(max_retries=1)
    )
    client.producer = DummyProducer()
    client.consumer = DummyConsumer()

    # ----------------------------
    # Produce a message
    # ----------------------------
    await client.produce("key1", {"foo": "bar"})
    assert len(produced_messages) == 1
    topic, key, value = produced_messages[0]
    assert topic == "test_topic"
    assert key == "key1"
    assert json.loads(value) == {"foo": "bar"}

    # ----------------------------
    # Consume message
    # ----------------------------
    consumed = []

    async def callback(k, v):
        consumed.append((k, v))

    await client.consume(callback)
    assert len(consumed) == 1
    k, v = consumed[0]
    assert k == "key1"
    assert v == {"foo": "bar"}
