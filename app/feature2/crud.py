# Simulated in-memory CRUD for orders
from typing import Dict, List

db: Dict[int, Dict] = {}
current_id = 1

def create_order(order_data: Dict) -> Dict:
    global current_id
    order = {"id": current_id, **order_data}
    db[current_id] = order
    current_id += 1
    return order

def get_order(order_id: int) -> Dict | None:
    return db.get(order_id)

def list_orders() -> List[Dict]:
    return list(db.values())
