# PyGem Messaging Annotation System

This project provides an **annotation-driven EventBus system** for Python applications, inspired by Java's Quarkus approach. It uses decorators to inject loggers, producers, consumers, and automatically manage singletons. Obviously, there is more to be done here, and any contributions are most welcome.

---

## Features

- **ApplicationScoped**: Automatically creates singleton-managed classes.
- **LoggerBinding**: Automatically injects a structured `JohnWickLogger` instance into classes or functions.
- **Producer / Consumer**: Decorators to produce and consume messages from the EventBus without boilerplate.
- **Inject**: Resolves dependencies from singletons or factory callables.
- **EventBusFactory**: Creates a configured EventBus based on YAML/properties configuration, supporting in-memory, Redis, and Kafka transports.
- **Subscribe**: Registers functions to automatically receive EventBus messages.

---

## Installation

1. Clone the repository:
```bash
git clone https://github.com/emmanuel-karanja/PyGem.git
```

2. Create a virtual environment and install dependencies and launch a container to run kafka, redis, and postgres:
```powershell

./build.ps1
```

This will install python if it's not installed, install the dependencies and also roll out kafka, postgresql and redis
within docker. You need to have docker installed.

3. Configure messaging in `messaging.eventbus.yml` or `messaging.eventbus.properties`. Example:
```yaml
messaging:
  eventbus:
    transport: kafka
kafka:
  bootstrap_servers: 127.0.0.1:9092
  group_id: default-group
  topic: default-topic
  dlq_topic: default-dlq
```

---

## Usage

### **1. Define a Singleton Service**
```python
from app.shared.annotations import ApplicationScoped, LoggerBinding

@ApplicationScoped
@LoggerBinding()
class OrderService:
    def __init__(self, logger=None, event_bus=None):
        self.logger = logger
        self.event_bus = event_bus

    async def place_order(self, order_id: str):
        self.logger.info(f"Placing order {order_id}")
        await self.event_bus.publish("order.placed", {"id": order_id})
```

### **2. Use Producer / Consumer Decorators**
```python
from app.shared.annotations import Producer, Consumer

@Producer(topic="order.placed")
class OrderProducer:
    pass  # auto-injects EventBus and provides .publish(payload) method

@Consumer(topic="order.placed")
async def handle_order(event):
    print("Received order:", event)
```

### **3. Inject Dependencies**
```python
from app.shared.annotations import Inject
from app.orders.order_service import OrderService

service = Inject(OrderService)  # returns singleton instance
await service.place_order("12345")
```

### **4. Startup Initialization in FastAPI**
```python
from fastapi import FastAPI
from app.shared.annotations import Inject
from app.orders.order_service import OrderService
from app.shared.messaging.event_bus_factory import EventBusFactory

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    Inject(OrderService)  # create singleton
    factory = Inject(EventBusFactory)
    factory.create_event_bus()  # ensures EventBus is ready
```

---

## EventBus Transports

- **In-memory**: Default fallback, no external dependencies.
- **Redis**: Supports pub/sub with `RedisClient`.
- **Kafka**: Async producer/consumer with retry, DLQ, batching, and metrics.

---

## Annotations Summary

| Annotation          | Usage                                    | Notes                                      |
|--------------------|-----------------------------------------|-------------------------------------------|
| `@ApplicationScoped` | Class                                   | Singleton-managed bean                     |
| `@LoggerBinding()`   | Class or function                       | Injects `JohnWickLogger`                  |
| `@Producer(topic)`   | Class                                   | Auto-injects EventBus and `.publish()`    |
| `@Consumer(topic)`   | Async function                          | Auto-subscribes to EventBus topic         |
| `Inject(cls_or_factory)` | Anywhere                            | Resolves singleton or calls factory       |
| `@Subscribe(event_name)` | Async function                        | Registers function for EventBus events    |

---

## Notes

- **EventBusFactory** is a singleton itself and auto-binds subscribers on creation.
- Consumers use `asyncio.create_task()` for fire-and-forget subscriptions.
- Producer classes get a convenience `.publish(payload)` method automatically.
- Logger injection respects existing `logger` parameters.

---

This system reduces boilerplate for messaging-heavy applications while maintaining Pythonic async patterns.

---

**Author:** Emmanuel  
**License:** MIT

## Flow

        ┌─────────────────────┐
        │ Your Application    │
        │ subscribe() / produce() │
        └─────────┬───────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │ KafkaEventBus       │
        │ - _ensure_topic_exists() ──┐  (dev-only → calls KafkaClient.create_topics)
        │ - start consume loop       │
        │ - publish() / subscribe()  │
        └─────────┬─────────────────┘
                  │
                  ▼
        ┌─────────────────────┐
        │ KafkaClient         │
        │ - create_topics()   │
        │ - produce(message)  │
        │ - consume()         │
        └─────────┬───────────┘
                  │
          Kafka Broker / Cluster
          ┌───────┴───────────┐
          │ Topics / Partitions │
          └───────┬───────────┘
                  │
        async message stream arrives
                  │
                  ▼
        ┌─────────────────────┐
        │ KafkaEventBus.consume_loop() │
        │ yields messages from consumer │
        └─────────┬─────────────────┘
                  │
          ┌───────┴─────────────┐
          │ Subscriber Callbacks │
          │  (async tasks)      │
          │ task1   task2   task3
          │  │       │       │
          ▼  ▼       ▼       ▼
     subscriber1()   subscriber2()   subscriber3()
          │   processing concurrently
          └─────────────┬─────────────┘
          asyncio.gather(*tasks, return_exceptions=True)
                  │
                  ▼
       Metrics incremented / logs updated
                  │
Next message arrives ──> repeat same async flow


