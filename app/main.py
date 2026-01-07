"""
Updated Main Application using PyGem Framework
Demonstrates the Quarkus-inspired bootstrapping.
"""

from app.application import PyGemApplication, create_app
from app.orders.order_service import OrderService
from app.notifications.notifications_service import NotificationService


# Define application routes
from fastapi import APIRouter

orders_router = APIRouter(prefix="/orders", tags=["orders"])

@orders_router.post("/{order_id}")
async def place_order(order_id: str):
    """Place a new order."""
    # Get service from CDI container
    from app.shared.pygem_simple import PyGem
    gem = PyGem()
    service = gem.get(OrderService)
    return await service.place_order(order_id)

@orders_router.get("/{order_id}")
async def get_order(order_id: str):
    """Get order by ID."""
    # This would fetch order from database
    return {"id": order_id, "status": "found"}


# Create application with all packages
pygem_app = create_app(["app.orders", "app.notifications", "app.shared"])

# Add routes
pygem_app.add_routes(orders_router)

# Expose the FastAPI app for uvicorn
app = pygem_app.app

# Run if executed directly
if __name__ == "__main__":
    pygem_app.run()