# 🏗️ PyGem Modular Monolith FastAPI Boilerplate


![CI](https://github.com/emmanuel-karanja/PyGem/actions/workflows/ci.yml/badge.svg)

A **bulletproof boilerplate template** for building **modular monoliths** in Python with **FastAPI**.  
Cobbled together from best practices and **extra-spiced with GenAI** for those cute ✅ / ❌ emojis.

---

## 🌟 Features

- **Modular Feature Architecture**  
  Organize your app by feature folders:  
  ```
  app/
    feature1/
    feature2/
    shared/
  ```
  Makes splitting features into microservices later trivial.

- **Async PostgreSQL Client**
  - Connection pooling ✅  
  - Retry policies ✅  
  - Batch & transaction support ✅  
  - COPY-based bulk insert for huge datasets ✅  

- **Redis Client**
  - Async support ✅  
  - TTL support ✅  
  - JSON serialization ✅  
  - Fully integrated structured logging ✅  

- **Event Bus**
  - Kafka and in-memory (Redis) event buses  
  - Fire-and-forget, safe subscribers ✅  
  - Retryable callbacks ✅  

- **Logging & Metrics**
  - `JohnWickLogger` for structured logs ✅  
  - Metrics collection for DB, Redis, and events ✅  

- **FastAPI Lifecycle Ready**
  - Startup/shutdown handled via **lifespan events**  
  - Automatic DB initialization, Redis connect, and Kafka startup  

- **Configuration**
  - `.env`-based settings  
  - `pydantic-settings` support ✅  

- **Test-Friendly**
  - Dependency injection for clients & services  
  - Dummy Redis/Kafka clients for tests ✅  

---

## ⚡ Quick Start

1. **Clone repo**
```bash
git clone https://github.com/emmanuel-karanja/PyGem.git
cd PyGem
```

2. **Install dependencies**
```PowerShell
./Setup.ps1 
```
That's it, it does everything including setting up python and the environment

3. **Configure environment**
 Modifythe `.env` file:
```
APP_NAME=ModularMonolithApp
DEBUG=True
REDIS_URL=redis://localhost:6379
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/mydatabase
KAFKA_BOOTSTRAP_SERVERS=localhost:9092
LOG_FILE=logs/app.log
LOG_LEVEL=INFO
```

4. **Run the application**
```.Run.ps1
```
✅ Visit `http://127.0.0.1:8000/docs` for auto-generated OpenAPI docs.

---

## 📦 Project Structure

```
app/
├── config/
│   ├── settings.py
│   ├── dependencies.py
│   ├── db_session.py          # Async SQLAlchemy session factory
│   └── factory.py             # DI factories for Redis, Kafka, Postgres, logger
├── feature1/
│   ├── models.py
│   ├── routes.py
│   └── services.py
├── feature2/
│   └── ...
├── shared/
│   ├── clients/
│   │   ├── redis_client.py    # Async Redis client with TTL & JSON
│   │   └── postgres_client.py # Async Postgres client with batching & metrics
│   ├── database/
│   │   └── base.py            # SQLAlchemy Base & engine setup
│   ├── event_bus/
│   │   ├── kafka_bus.py       # Async Kafka event bus
│   │   └── inprocess.py       # In-memory event bus
│   ├── metrics/
│   │   └── metrics_collector.py # Tracks successes/failures/processed
│   └── logger/
│       └── bulletproof_logger.py
└── main.py

```

---

## 🚀 Features in Action

### Redis Example
```python
from app.config.factory import get_redis_client

redis = get_redis_client()
await redis.set("foo", {"bar": 123}, ttl=60)
value = await redis.get("foo")
```

### Kafka Example
```python
from app.config.factory import get_kafka_event_bus

bus = get_kafka_event_bus()

async def handle_event(payload):
    print("Received event:", payload)

await bus.subscribe("feature_events", handle_event)
await bus.publish("feature_events", {"msg": "Hello world"})
```

### Postgres Example
```python
from app.config.dependencies import async_sessionmaker
from app.shared.database.postgres_client import PostgresClient

pg = PostgresClient(dsn="postgresql+asyncpg://user:password@localhost/db")

await pg.execute("INSERT INTO users (name) VALUES ($1)", "Alice")
rows = await pg.fetch("SELECT * FROM users")
```

---

## 📊 Metrics & Logging
- All DB, Redis, and EventBus operations are tracked with **MetricsCollector**.
- Logs are structured and saved to `logs/app.log`.
- Global logger: `JohnWickLogger` for unified logging.

---

## 🧪 Testing
- Supports pytest with **dummy clients** for Redis/Kafka.
- Example:
```python
import pytest
from app.shared.clients.redis_client import RedisClient

@pytest.mark.asyncio
async def test_redis_set_get_delete():
    client = RedisClient()
    await client.set("test", {"x": 1})
    val = await client.get("test")
    assert val == {"x": 1}
```

---

## 🎯 Why This Template?
- Saves hours of setup ✅  
- Implements production-grade async patterns ✅  
- If not for anything the JohnWickLogger is pretty dope!
- Modular & scalable for microservices l

# JohnWickLogger Documentation

## Logging with JohnWickLogger

`JohnWickLogger` is a custom logger for this project that provides:

- JSON logs for file handlers
- Colorized logs for console output
- Support for `extra` metadata for structured logging

---

## Initialization

```python
from app.shared.logger.john_wick_logger import JohnWickLogger

logger = JohnWickLogger(
    name="app_logger",
    log_file="app.log",
    json_format=True  # Use JSON for console, too
)
```

---

## Logging Methods

`JohnWickLogger` keeps the standard logging interface:

```python
logger.debug("Debug message", extra={"class_name": "MyClass"})
logger.info("Info message", extra={"user_id": 42})
logger.warning("Warning message")
logger.error("Error message")
logger.exception("Exception message")
```

- All methods accept an optional `extra` dictionary for structured metadata.
- `class_name`, `module_name`, or request-specific identifiers can be included.

---

## Example: Adding Extras

```python
class FeatureService:
    def __init__(self):
        self.logger = logger

    def process(self, user_id: int):
        self.logger.info(
            "Processing user request",
            extra={"class_name": self.__class__.__name__, "user_id": user_id}
        )

service = FeatureService()
service.process(user_id=42)
```

**File output (JSON):**

```json
{
  "timestamp": "2025-09-25T12:30:01",
  "level": "INFO",
  "name": "app_logger",
  "message": "Processing user request",
  "extra": {
    "class_name": "FeatureService",
    "user_id": 42
  }
}
```

**Console output (colorized):**

```
2025-09-25 12:30:01 - app_logger - INFO - Processing user request
```

---

## Best Practices

- Always include `class_name` or `module_name` in `extra` for traceability. NB: We could have added automation for this,but
  it'd require walking the stack which adds some overhead, improves to come soon.
- Include request or user identifiers for distributed tracing.
- Avoid logging sensitive information like passwords or secr