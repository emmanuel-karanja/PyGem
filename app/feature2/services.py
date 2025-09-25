from app.feature2.crud import create_order, get_order, list_orders
from app.config.factory import get_logger, get_kafka_event_bus

logger = get_logger("feature2_service")
event_bus = get_kafka_event_bus(logger)

async def place_order(order_data: dict) -> dict:
    order = create_order(order_data)
    # Publish event to Kafka for processing
    await event_bus.publish("orders", order)
    logger.info("Order placed", extra={"order_id": order["id"]})
    return order

async def retrieve_order(order_id: int) -> dict | None:
    return get_order(order_id)

async def list_all_orders() -> list[dict]:
    return list_orders()
