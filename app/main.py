from fastapi import FastAPI
from app.shared.annotations import Inject
from app.orders.order_service import OrderService
from app.notifications.notifications_servixe import NotificationService

app = FastAPI()

# Force creation of singletons at startup
@app.on_event("startup")
async def startup_event():
    Inject(OrderService)         # initializes OrderService singleton
    Inject(NotificationService)  # initializes NotificationService singleton
    # No need to manually call create_event_bus; decorators handle it

@app.post("/orders/{order_id}")
async def place_order(order_id: str):
    service = Inject(OrderService)  # retrieves the singleton instance
    return await service.place_order(order_id)
