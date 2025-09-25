from fastapi import APIRouter
from app.feature2.services import place_order, retrieve_order, list_all_orders

router = APIRouter()

@router.post("/orders")
async def create_order_endpoint(payload: dict):
    return await place_order(payload)

@router.get("/orders/{order_id}")
async def get_order_endpoint(order_id: int):
    order = await retrieve_order(order_id)
    if order is None:
        return {"error": "Order not found"}
    return order

@router.get("/orders")
async def list_orders_endpoint():
    return await list_all_orders()
