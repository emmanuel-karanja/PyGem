from fastapi import FastAPI
from app.shared.annotations.messaging import _CONSUMER_REGISTRY, register_consumers
from app.shared.annotations.core import Inject
from app.orders.order_service import OrderService
from app.notifications.notifications_service import NotificationService
from app.shared.messaging.event_bus_factory import EventBusFactory

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """
    - Initializes all singleton services.
    - EventBus creation is handled automatically via Producer/Consumer/Subscribe decorators.
    - Consumers are automatically registered to the EventBus.
    """
    # Initialize singletons
    Inject(OrderService)
    Inject(NotificationService)

    # Retrieve EventBus and register consumer methods
    Inject(EventBusFactory).create_event_bus()
    await register_consumers()  # Binds @Consumer methods to topics
    print(_CONSUMER_REGISTRY)


@app.post("/orders/{order_id}")
async def place_order(order_id: str):
    # Retrieve singleton instance of OrderService
    service = Inject(OrderService)
    return await service.place_order(order_id)
