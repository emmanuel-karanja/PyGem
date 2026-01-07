from app.shared.annotations import RequestScoped, LoggerBinding, Producer
from app.shared.logger import JohnWickLogger


@RequestScoped
@LoggerBinding()  # auto-injects logger
@Producer(topic="order.placed")  # auto-injects EventBus and sets topic
class OrderService:
    def __init__(self, logger: JohnWickLogger = None, event_bus=None):
        """
        - logger is injected by LoggerBinding
        - event_bus is injected by Producer
        """
        self.logger = logger
        self.event_bus = event_bus

    async def place_order(self, order_id: str):
        """
        Publishes an order.placed event on the EventBus.
        """
        self.logger.info(f"Placing order {order_id}")
        # Producer decorator has already injected the event_bus and topic
        await self.publish({"id": order_id})
        return {"status": "ok", "order_id": order_id}
