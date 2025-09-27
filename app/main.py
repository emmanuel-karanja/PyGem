from fastapi import FastAPI
from app.shared.annotations.messaging import _CONSUMER_REGISTRY, register_consumers
from app.orders.order_service import OrderService
from app.notifications.notifications_service import NotificationService
from app.shared.messaging.event_bus_factory import EventBusFactory
from app.shared.pygem import PyGem

app = FastAPI()
gem = PyGem()

@app.on_event("startup")
async def startup_event():
    """
    - Initializes all singleton services.
    - EventBus creation is handled automatically via Producer/Consumer/Subscribe decorators.
    - Consumers are automatically registered to the EventBus.
    """
    # Initialize singletons via PyGem
    gem.get(OrderService)
    gem.get(NotificationService)

    # Autowire and initialize EventBus
    event_bus_factory = gem.get(EventBusFactory)
    event_bus_factory.create_event_bus()

    # Register all consumers with the EventBus
    await register_consumers()
    print("Consumers:", _CONSUMER_REGISTRY)


@app.post("/orders/{order_id}")
async def place_order(order_id: str):
    # Retrieve singleton instance of OrderService via PyGem
    service = gem.get(OrderService)
    return await service.place_order(order_id)
