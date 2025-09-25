import pytest
import json

from app.shared.clients.kafka_client import KafkaClient
from app.shared.retry import ExponentialBackoffRetry
from app.config.logger import logger


@pytest.mark.asyncio
async def test_produce_consume():
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
            for topic, key, value in produced_messages:  # FIXED: unpack 3 values
                class Msg:
                    def __init__(self, key, value):
                        self.key = key
                        self.value = value
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
        retry_policy=ExponentialBackoffRetry(max_retries=1),
        batch_size=1,
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
    assert key == b"key1"
    assert value == json.dumps({"foo": "bar"}).encode()

    # ----------------------------
    # Consume message deterministically
    # ----------------------------
    consumed = []

    async def callback(k, v):
        consumed.append((k, v))

    await client._consume_loop(callback)

    assert len(consumed) == 1
    assert consumed[0][0] == "key1"
    assert consumed[0][1] == {"foo": "bar"}
